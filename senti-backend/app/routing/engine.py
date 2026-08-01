"""Motor de rutas de menor riesgo (§20).

Implementa el flujo del §20.1 tal cual:

    Origen, destino y perfil del hogar
          ↓
    Cierres confirmados → exclude_polygons / exclude_locations en la PETICIÓN
          ↓
    Costing según medio de transporte y accesibilidad del hogar
          ↓
    Valhalla genera rutas candidatas
          ↓
    PostGIS cruza cada polilínea con zonas de peligro amplias y reportes vigentes
          ↓
    Descarte duro y penalización blanda
          ↓
    Puntaje → ruta recomendada + alternativa

Todo el juicio vive en `app.rules.scoring`, que es determinista y está probado.
Este módulo solo consigue los hechos y los pone en su sitio.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from geoalchemy2 import Geography
from geoalchemy2.shape import from_shape
from shapely.geometry import LineString, Point
from sqlalchemy import case, cast, func, select
from sqlalchemy.orm import Session

from app.domain import ConfidenceLevel, HazardType, TrustLevel
from app.models import CitizenReport, Hazard, Resource, RoadBlock, Route, RouteSegment
from app.models.base import SRID
from app.rules import scoring
from app.rules.scoring import (
    HouseholdFacts,
    RankingResult,
    ReportRisk,
    RouteFacts,
    SegmentFacts,
)
from app.routing.valhalla import (
    SinRutaValhalla,
    ValhallaClient,
    ValhallaRoute,
    costing_para_perfil,
)

logger = logging.getLogger(__name__)
GEOGRAPHY = Geography(srid=SRID)

# §20.3: "reporte ... a menos de 200 m".
RADIO_REPORTE_M = scoring.RADIO_REPORTE_M

# §20.4: umbral de cobertura cartográfica. Se registra por distrito antes del
# piloto; estos son los valores de arranque.
UMBRAL_DENSIDAD_VIAS_KM2 = 3.0
UMBRAL_PCT_VIAS_ETIQUETADAS = 0.6


@dataclass
class CoberturaCartografica:
    """§20.4. Bajo el umbral, la respuesta cambia de "esta es la ruta" a
    "esta es una ruta posible; la cartografía de la zona es incompleta"."""

    densidad_vias_km2: float
    pct_vias_etiquetadas: float
    tiene_elevacion: bool
    suficiente: bool

    @property
    def frase(self) -> str:
        if self.suficiente:
            return (
                "Esta es la ruta de menor riesgo según la información disponible "
                "y su última actualización."
            )
        return (
            "Esta es una ruta posible; la cartografía de la zona es incompleta, "
            "así que la información puede no reflejar el estado real de la vía."
        )


@dataclass
class ResultadoRuta:
    ranking: RankingResult
    rutas_valhalla: dict[str, ValhallaRoute]
    cobertura: CoberturaCartografica
    fuentes: list[dict]
    sin_ruta_verificable: bool
    motivo_sin_ruta: str | None = None
    # Cierres alrededor del origen, para pintarlos en el mapa del cliente.
    # No participan en el cálculo: ya se aplicaron como exclusión (§20.1) o
    # como penalización (§21.2). Esto es solo lo que hay que poder ver.
    bloqueos_dibujables: list[dict] = field(default_factory=list)


class RouteEngine:
    def __init__(self, session: Session, valhalla: ValhallaClient | None = None) -> None:
        self.session = session
        self.valhalla = valhalla or ValhallaClient()

    # ── 1. Cierres → exclusiones en la petición (§20.1) ────────────────────
    def _cierres_vinculantes(self, ahora: datetime) -> list[RoadBlock]:
        """Cierres oficiales o municipales vigentes.

        Solo estos entran como exclusión: el §6 dice que solo el operador
        municipal o una fuente oficial cierran una vía, y el §21.2 que un
        reporte validado penaliza pero no excluye.
        """
        stmt = select(RoadBlock).where(
            RoadBlock.vigente.is_(True),
            RoadBlock.confianza.in_([ConfidenceLevel.OFICIAL, ConfidenceLevel.MUNICIPAL]),
            RoadBlock.inicio_at <= ahora,
            (RoadBlock.fin_at.is_(None)) | (RoadBlock.fin_at >= ahora),
            RoadBlock.reabierto_at.is_(None),
        )
        return list(self.session.scalars(stmt))

    def _exclusiones(
        self, cierres: list[RoadBlock]
    ) -> tuple[list[tuple[float, float]], list[list[tuple[float, float]]]]:
        puntos: list[tuple[float, float]] = []
        poligonos: list[list[tuple[float, float]]] = []

        for cierre in cierres:
            if cierre.punto is not None:
                geom = self.session.scalar(select(func.ST_AsText(cierre.punto)))
                p = _punto_desde_wkt(geom)
                if p:
                    puntos.append(p)
            elif cierre.poligono is not None:
                wkt = self.session.scalar(select(func.ST_AsText(cierre.poligono)))
                anillo = _anillo_desde_wkt(wkt)
                if anillo:
                    poligonos.append(anillo)

        return puntos, poligonos

    # ── 2. Cruce PostGIS de cada polilínea (§20.1) ─────────────────────────
    def _hechos_de_ruta(
        self,
        ruta_id: str,
        ruta: ValhallaRoute,
        ahora: datetime,
        *,
        destino_validado: bool,
        orden_evacuacion_contraria: bool,
    ) -> RouteFacts:
        """Cruza la polilínea contra hazards, reportes y cierres, y arma los
        hechos que el §20.3 necesita.

        Se hace por maniobra y no por ruta entera a propósito: `S_seguridad`
        toma el máximo de riesgo **de cualquier tramo**, así que agregar antes
        de tiempo perdería el pico que decide el puntaje.
        """
        if len(ruta.puntos) < 2:
            return RouteFacts(id=ruta_id, segmentos=(), distancia_m=ruta.distancia_m,
                              duracion_s=ruta.duracion_s)

        linea = LineString([(lon, lat) for lat, lon in ruta.puntos])
        geom_ruta = from_shape(linea, srid=SRID)

        segmentos: list[SegmentFacts] = []
        oficiales = comunitarios = 0

        for m in ruta.maniobras or [None]:
            if m is None:
                sub = linea
            else:
                trozo = ruta.puntos[m.begin_shape_index : m.end_shape_index + 1]
                if len(trozo) < 2:
                    continue
                sub = LineString([(lon, lat) for lat, lon in trozo])
            geom_sub = from_shape(sub, srid=SRID)

            # Zona de peligro amplia (§20.1: se resuelve aquí, no en Valhalla).
            peligro_alto = self.session.scalar(
                select(func.count(Hazard.id)).where(
                    Hazard.activo.is_(True),
                    Hazard.peligro_alto.is_(True),
                    (Hazard.vigencia_fin.is_(None)) | (Hazard.vigencia_fin >= ahora),
                    func.ST_Intersects(Hazard.geom, geom_sub),
                )
            ) or 0

            # Cierre vigente que el motor no excluyó (p. ej. recortado por
            # max_exclude_polygons). Aquí se atrapa y provoca descarte duro.
            cierre = self.session.scalar(
                select(func.count(RoadBlock.id)).where(
                    RoadBlock.vigente.is_(True),
                    RoadBlock.confianza.in_(
                        [ConfidenceLevel.OFICIAL, ConfidenceLevel.MUNICIPAL]
                    ),
                    RoadBlock.reabierto_at.is_(None),
                    func.ST_DWithin(
                        func.coalesce(RoadBlock.punto, RoadBlock.poligono).cast(GEOGRAPHY),
                        cast(geom_sub, GEOGRAPHY),
                        25.0,
                    ),
                )
            ) or 0
            if cierre:
                oficiales += cierre

            # Reportes ciudadanos vigentes a menos de 200 m (§20.3).
            filas = self.session.execute(
                select(
                    CitizenReport.trust_level,
                    CitizenReport.tipo,
                    CitizenReport.reportado_at,
                    func.ST_Distance(
                        CitizenReport.geom.cast(GEOGRAPHY),
                        cast(geom_sub, GEOGRAPHY),
                    ).label("dist"),
                ).where(
                    CitizenReport.estado.notin_(["rechazado", "duplicado", "desactualizado"]),
                    (CitizenReport.vence_at.is_(None)) | (CitizenReport.vence_at >= ahora),
                    func.ST_DWithin(
                        CitizenReport.geom.cast(GEOGRAPHY),
                        cast(geom_sub, GEOGRAPHY),
                        RADIO_REPORTE_M,
                    ),
                )
            ).all()

            reportes = tuple(
                ReportRisk(
                    trust_level=TrustLevel(nivel) if not isinstance(nivel, TrustLevel) else nivel,
                    tipo=HazardType(tipo) if not isinstance(tipo, HazardType) else tipo,
                    reportado_at=reportado,
                    distancia_m=float(dist),
                )
                for nivel, tipo, reportado, dist in filas
            )
            comunitarios += len(reportes)

            segmentos.append(
                SegmentFacts(
                    cruza_cierre_vigente=bool(cierre),
                    intersecta_zona_peligro_alto=bool(peligro_alto),
                    reportes_cercanos=reportes,
                    # La pendiente real la entrega Valhalla con elevación
                    # habilitada; hasta que el build de teselas incluya
                    # elevación se deja en 0 y `S_accesible` no penaliza por
                    # un dato que no existe.
                    pendiente_max_pct=0.0,
                    tiene_escaleras=_maniobra_con_escaleras(m),
                    superficie_irregular=False,
                )
            )

        # §20.2: requiere cruzar agua / puente afectado / quebrada activada.
        cruza_agua = self._cruza_hazard(geom_ruta, HazardType.INUNDACION, ahora)
        puente = self._cruza_hazard(geom_ruta, HazardType.PUENTE_AFECTADO, ahora)
        quebrada = self._cruza_hazard(geom_ruta, HazardType.HUAICO, ahora)

        return RouteFacts(
            id=ruta_id,
            segmentos=tuple(segmentos),
            distancia_m=ruta.distancia_m,
            duracion_s=ruta.duracion_s,
            atraviesa_puente_afectado=puente,
            entra_quebrada_activada=quebrada,
            requiere_cruzar_agua=cruza_agua,
            contradice_orden_evacuacion=orden_evacuacion_contraria,
            destino_validado=destino_validado,
            bloqueos_de_fuente_oficial=oficiales,
            bloqueos_de_fuente_comunitaria=comunitarios,
            hay_informacion_reciente_zona=True,
        )

    def _cruza_hazard(self, geom, tipo: HazardType, ahora: datetime) -> bool:
        n = self.session.scalar(
            select(func.count(Hazard.id)).where(
                Hazard.activo.is_(True),
                Hazard.tipo == tipo,
                Hazard.peligro_alto.is_(True),
                (Hazard.vigencia_fin.is_(None)) | (Hazard.vigencia_fin >= ahora),
                func.ST_Intersects(Hazard.geom, geom),
            )
        )
        return bool(n)

    # ── 3. Cobertura cartográfica (§20.4) ──────────────────────────────────
    def cobertura(self, distrito: str | None) -> CoberturaCartografica:
        """§20.4: umbral de cobertura cartográfica, por distrito.

        El §20.4 dice que "el umbral se registra por distrito antes del
        piloto", así que la fuente de verdad es `risk_parameters`, que el
        administrador versiona (§23). Antes esto solo comparaba el nombre del
        distrito con el del piloto, lo que declaraba buena la cobertura de
        Chosica sin haber medido nada.

        Sin registro para el distrito, se asume **insuficiente**. Es la
        asimetría que impone el §20.4: decir "esta es una ruta posible, la
        cartografía es incompleta" cuando en realidad era buena solo suena
        prudente de más; decir "esta es la ruta" sobre cartografía incompleta
        manda a alguien por una vía que quizá no existe.
        """
        registro = self._umbral_registrado(distrito)
        if registro is None:
            return CoberturaCartografica(
                densidad_vias_km2=0.0,
                pct_vias_etiquetadas=0.0,
                tiene_elevacion=False,
                suficiente=False,
            )

        densidad = float(registro.get("densidad_vias_km2", 0.0))
        etiquetadas = float(registro.get("pct_vias_etiquetadas", 0.0))
        elevacion = bool(registro.get("tiene_elevacion", False))
        return CoberturaCartografica(
            densidad_vias_km2=densidad,
            pct_vias_etiquetadas=etiquetadas,
            tiene_elevacion=elevacion,
            suficiente=(
                densidad >= UMBRAL_DENSIDAD_VIAS_KM2
                and etiquetadas >= UMBRAL_PCT_VIAS_ETIQUETADAS
            ),
        )

    def _umbral_registrado(self, distrito: str | None) -> dict | None:
        """Lee la medición del distrito de los parámetros activos (§23)."""
        if not distrito:
            return None
        from app.models import RiskParameters

        parametros = self.session.scalar(
            select(RiskParameters).where(RiskParameters.activo.is_(True))
        )
        if parametros is None or not parametros.umbrales_cobertura:
            return None

        # Coincidencia sin distinguir mayúsculas ni tildes: el distrito llega
        # del perfil del hogar, que lo escribe una persona.
        objetivo = _normalizar_distrito(distrito)
        for nombre, valores in parametros.umbrales_cobertura.items():
            if _normalizar_distrito(nombre) == objetivo:
                return valores if isinstance(valores, dict) else None
        return None

    # ── Orquestación completa ──────────────────────────────────────────────
    def bloqueos_cerca(
        self, origen: tuple[float, float], ahora: datetime, radio_m: float = 3000.0
    ) -> list[dict]:
        """Cierres vigentes alrededor de quien pregunta, para dibujarlos.

        Incluye los comunitarios validados además de los vinculantes. En el
        cálculo no pesan igual —el §21.2 dice que un reporte validado penaliza
        pero no excluye— y por eso van marcados con `vinculante`: el mapa los
        pinta distinto. Ocultarlos sería peor que mostrarlos matizados, porque
        el §20.5 prohíbe presentar el silencio como ausencia de peligro.
        """
        punto = from_shape(Point(origen[1], origen[0]), srid=SRID)
        geom = func.coalesce(RoadBlock.punto, RoadBlock.poligono)
        # RoadBlock no guarda un radio: guarda un punto o un polígono. El radio
        # con el que se dibuja se deriva de la geometría —para un polígono, el
        # de un círculo de su misma área— porque el cliente pinta círculos y
        # necesita un número, no porque el cierre sea circular.
        radio = case(
            (
                RoadBlock.poligono.isnot(None),
                func.sqrt(func.ST_Area(cast(RoadBlock.poligono, GEOGRAPHY)) / 3.14159),
            ),
            else_=60.0,
        )
        filas = self.session.execute(
            select(
                RoadBlock.confianza,
                RoadBlock.motivo,
                RoadBlock.nombre_via,
                func.ST_Y(func.ST_Centroid(geom)),
                func.ST_X(func.ST_Centroid(geom)),
                radio,
            ).where(
                RoadBlock.vigente.is_(True),
                RoadBlock.reabierto_at.is_(None),
                RoadBlock.inicio_at <= ahora,
                (RoadBlock.fin_at.is_(None)) | (RoadBlock.fin_at >= ahora),
                func.ST_DWithin(cast(geom, GEOGRAPHY), cast(punto, GEOGRAPHY), radio_m),
            )
        ).all()

        return [
            {
                "lat": float(lat),
                "lon": float(lon),
                "radio_m": max(float(r or 60.0), 25.0),
                "motivo": via or motivo.value.replace("_", " "),
                "vinculante": conf
                in (ConfidenceLevel.OFICIAL, ConfidenceLevel.MUNICIPAL),
            }
            for conf, motivo, via, lat, lon, r in filas
            if lat is not None and lon is not None
        ]

    def calcular(
        self,
        origen: tuple[float, float],
        destino: tuple[float, float],
        hogar: HouseholdFacts,
        ahora: datetime,
        *,
        distrito: str | None = None,
        destino_resource_id=None,
        orden_evacuacion_contraria: bool = False,
        evitar: list[tuple[float, float]] | None = None,
    ) -> ResultadoRuta:
        """Calcula la ruta.

        `evitar` son puntos que el usuario ha marcado como intransitables
        **desde el mapa, para esta petición suya y solo para ella**.

        No crea ningún cierre y no cambia la ruta de nadie más. El §6 reserva
        cerrar una vía al operador municipal o a una fuente oficial, y el §21.2
        dice que un reporte sin confirmar penaliza pero no excluye — eso sigue
        intacto: el reporte que se manda en paralelo entra sin confirmar y pesa
        lo que le toca en el sistema.

        Lo que sí puede hacer alguien es negarse a pasar por donde está viendo
        que no se pasa. Ignorarlo tendría el efecto contrario al que busca el
        §20: devolverle una y otra vez la ruta que acaba de decir que está
        cortada, hasta que deje de preguntar.
        """
        cierres = self._cierres_vinculantes(ahora)
        puntos, poligonos = self._exclusiones(cierres)
        if evitar:
            # Se acotan para que una petición no pueda dejar sin ruta a su
            # propio autor por acumulación, ni convertirse en una forma de
            # cargar el motor con cientos de exclusiones.
            puntos.extend(evitar[:24])
        costing, opciones = costing_para_perfil(
            vehiculo=hogar.vehiculo,
            movilidad_reducida=hogar.movilidad_reducida,
            adultos_mayores=hogar.adultos_mayores,
        )

        # §20.2: "conduce a un destino no validado" es descarte duro. Se
        # comprueba antes de gastar una llamada a Valhalla.
        destino_validado = True
        if destino_resource_id is not None:
            recurso = self.session.get(Resource, destino_resource_id)
            destino_validado = bool(recurso and recurso.validado and recurso.disponible)

        try:
            rutas = self.valhalla.route(
                origen,
                destino,
                costing=costing,
                costing_options=opciones,
                exclude_locations=puntos,
                exclude_polygons=poligonos,
            )
        except SinRutaValhalla as exc:
            return ResultadoRuta(
                ranking=RankingResult(None, None, ()),
                rutas_valhalla={},
                cobertura=self.cobertura(distrito),
                fuentes=_fuentes_de_cierres(cierres),
                sin_ruta_verificable=True,
                motivo_sin_ruta=str(exc),
                bloqueos_dibujables=self.bloqueos_cerca(origen, ahora),
            )

        por_id = {f"r{i}": r for i, r in enumerate(rutas)}
        hechos = [
            self._hechos_de_ruta(
                rid,
                r,
                ahora,
                destino_validado=destino_validado,
                orden_evacuacion_contraria=orden_evacuacion_contraria,
            )
            for rid, r in por_id.items()
        ]

        ranking = scoring.rankear(hechos, hogar, ahora)

        return ResultadoRuta(
            ranking=ranking,
            rutas_valhalla=por_id,
            cobertura=self.cobertura(distrito),
            fuentes=_fuentes_de_cierres(cierres),
            sin_ruta_verificable=ranking.sin_ruta_verificable,
            motivo_sin_ruta=(
                "todas las rutas candidatas fueron descartadas"
                if ranking.sin_ruta_verificable
                else None
            ),
            bloqueos_dibujables=self.bloqueos_cerca(origen, ahora),
        )

    # ── Persistencia (§23: la ruta debe poder explicarse después) ──────────
    def guardar(
        self,
        resultado: ResultadoRuta,
        *,
        user_id=None,
        incident_id=None,
        origen: tuple[float, float],
        destino: tuple[float, float],
        costing: str,
        parametros_version: str = "v1",
    ) -> Route | None:
        if resultado.ranking.recomendada is None:
            return None

        puntaje = resultado.ranking.recomendada
        valhalla_route = resultado.rutas_valhalla[puntaje.ruta_id]
        linea = LineString([(lon, lat) for lat, lon in valhalla_route.puntos])

        route = Route(
            user_id=user_id,
            incident_id=incident_id,
            origen=from_shape(Point(origen[1], origen[0]), srid=SRID),
            destino=from_shape(Point(destino[1], destino[0]), srid=SRID),
            costing=costing,
            geometria=from_shape(linea, srid=SRID),
            distancia_m=valhalla_route.distancia_m,
            duracion_s=valhalla_route.duracion_s,
            s_seguridad=puntaje.s_seguridad,
            s_fuente=puntaje.s_fuente,
            s_accesible=puntaje.s_accesible,
            s_duracion=puntaje.s_duracion,
            s_distancia=puntaje.s_distancia,
            puntaje=puntaje.puntaje,
            recomendada=True,
            descartada=False,
            nivel_confianza=_nivel_confianza(puntaje.puntaje, resultado.cobertura.suficiente),
            cobertura_suficiente=resultado.cobertura.suficiente,
            parametros_version=parametros_version,
            pesos=dict(scoring.PESOS),
            bloqueos_considerados=[
                {"ruta": rid, "motivo": motivo} for rid, motivo in resultado.ranking.descartadas
            ],
            fuentes_citadas=resultado.fuentes,
            explicacion=puntaje.motivo_riesgo_maximo,
        )
        self.session.add(route)
        self.session.flush()

        for i, m in enumerate(valhalla_route.maniobras):
            self.session.add(
                RouteSegment(
                    route_id=route.id,
                    orden=i,
                    instruccion=m.instruccion,
                    distancia_m=m.distancia_m,
                    riesgo=0.0,
                )
            )
        return route


def _normalizar_distrito(nombre: str) -> str:
    import unicodedata

    d = unicodedata.normalize("NFD", nombre.strip().lower())
    return "".join(c for c in d if unicodedata.category(c) != "Mn")


def _nivel_confianza(puntaje: float, cobertura_ok: bool) -> str:
    """§20.5: nivel de confianza mostrado al usuario."""
    if not cobertura_ok:
        return "bajo"
    if puntaje >= 0.85:
        return "alto"
    if puntaje >= 0.6:
        return "medio"
    return "bajo"


def _fuentes_de_cierres(cierres: list[RoadBlock]) -> list[dict]:
    return [
        {
            "tipo": "cierre",
            "confianza": c.confianza.value,
            "via": c.nombre_via,
            "motivo": c.motivo.value,
            "desde": c.inicio_at.isoformat() if c.inicio_at else None,
        }
        for c in cierres
    ]


def _maniobra_con_escaleras(m) -> bool:
    if m is None:
        return False
    texto = (m.instruccion or "").lower()
    return "escalera" in texto or "escalones" in texto


def _punto_desde_wkt(wkt: str | None) -> tuple[float, float] | None:
    if not wkt or not wkt.upper().startswith("POINT"):
        return None
    interior = wkt[wkt.index("(") + 1 : wkt.index(")")]
    lon, lat = (float(v) for v in interior.split())
    return (lat, lon)


def _anillo_desde_wkt(wkt: str | None) -> list[tuple[float, float]] | None:
    if not wkt or "POLYGON" not in wkt.upper():
        return None
    interior = wkt[wkt.index("((") + 2 : wkt.index("))")]
    puntos = []
    for par in interior.split(","):
        lon, lat = (float(v) for v in par.strip().split())
        puntos.append((lat, lon))
    return puntos or None
