"""Implementación de las nueve herramientas del §16.

Cada handler devuelve un `ToolResult` con datos ya verificados y las fuentes
que los respaldan. Ninguno devuelve texto redactado: eso lo hace el modelo
después, sobre este resultado (§8).

Cuando no hay dato, se devuelve `ausencia` con una frase explícita en vez de un
resultado vacío. El §11.3 lo exige — "nunca presenta silencio como ausencia de
peligro" — y en la práctica evita que el modelo rellene el hueco por su cuenta.
"""

from __future__ import annotations

import ipaddress
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx
from geoalchemy2 import Geography
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import case, cast, func, or_, select, text

from app.core.security import Permission
from app.domain import ConfidenceLevel, HazardType, TrustLevel
from app.models import (
    Alert,
    AlertZone,
    CitizenReport,
    EmergencyPhone,
    HouseholdProfile,
    OfficialSource,
    Protocol,
    Resource,
    RoadBlock,
)
from app.models.base import SRID
from app.orchestrator.tools import (
    MensajeContactoArgs,
    OfflineArgs,
    PlanArgs,
    RecursosArgs,
    ReporteArgs,
    RutaArgs,
    SinArgs,
    ToolContext,
    ToolResult,
    WebOficialArgs,
    ZonaArgs,
    herramienta,
)
from app.rules import phones
from app.rules.scoring import HouseholdFacts
from app.sources.health import declarar_ausencia

GEOGRAPHY = Geography(srid=SRID)
WEB_TIMEOUT_S = 8.0
WEB_MAX_BYTES = 256_000
WEB_MAX_CHARS = 1800


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._ignorar = 0
        self.partes: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._ignorar += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._ignorar:
            self._ignorar -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignorar:
            texto = " ".join(data.split())
            if texto:
                self.partes.append(texto)


def _dominio_de(url: str) -> str:
    parsed = urlparse(url)
    return (parsed.hostname or "").lower().rstrip(".")


def _dominio_publico_permitido(dominio: str) -> bool:
    if not dominio or dominio in {"localhost", "127.0.0.1", "::1"}:
        return False
    try:
        ip = ipaddress.ip_address(dominio)
    except ValueError:
        return True
    return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved)


def _dominio_autorizado(dominio: str, dominios_permitidos: set[str]) -> bool:
    return any(
        dominio == permitido or dominio.endswith(f".{permitido}")
        for permitido in dominios_permitidos
    )


def _texto_visible(contenido: bytes, content_type: str) -> str:
    texto = contenido.decode("utf-8", errors="replace")
    if "html" not in content_type.lower():
        return " ".join(texto.split())[:WEB_MAX_CHARS]
    parser = _TextExtractor()
    parser.feed(texto)
    return " ".join(parser.partes)[:WEB_MAX_CHARS]


def _dominios_oficiales(ctx: ToolContext) -> set[str]:
    fuentes = ctx.session.scalars(select(OfficialSource).where(OfficialSource.activa.is_(True)))
    dominios: set[str] = set()
    for fuente in fuentes:
        for url in (fuente.url, fuente.healthcheck_url):
            dominio = _dominio_de(url or "")
            if _dominio_publico_permitido(dominio):
                dominios.add(dominio.removeprefix("www."))
    return dominios


# ── 1. consultar_alerta_actual(zona) ───────────────────────────────────────
@herramienta(
    "consultar_alerta_actual",
    "Devuelve las alertas oficiales vigentes que incluyen una zona o distrito. "
    "Úsala siempre antes de afirmar que hay o no hay alerta.",
    ZonaArgs,
    Permission.CONSULTAR_ALERTAS,
)
def consultar_alerta_actual(ctx: ToolContext, args: ZonaArgs) -> ToolResult:
    """§15: la pregunta «¿esta alerta afecta mi zona?» se responde con PostGIS,
    no con el criterio del modelo."""
    zona = args.zona.strip()
    stmt = (
        select(Alert, AlertZone)
        .join(AlertZone, AlertZone.alert_id == Alert.id)
        .where(
            Alert.vigente.is_(True),
            or_(Alert.vigencia_fin.is_(None), Alert.vigencia_fin >= ctx.ahora),
            or_(
                func.lower(AlertZone.distrito) == zona.lower(),
                func.lower(AlertZone.nombre).contains(zona.lower()),
            ),
        )
    )
    filas = ctx.session.execute(stmt).all()

    if not filas:
        return ToolResult(
            ok=True,
            datos={"zona": zona, "alertas": []},
            ausencia=(
                f"No hay alerta oficial vigente registrada para {zona}. "
                f"La ausencia de alerta no significa ausencia de peligro."
            ),
        )

    alertas = []
    fuentes = []
    for alerta, zona_geom in filas:
        alertas.append(
            {
                "id": str(alerta.id),
                "tipo": alerta.tipo_evento.value,
                "titulo": alerta.titulo,
                "nivel_oficial": alerta.nivel_oficial,
                "entidad": alerta.entidad_emisora,
                "confianza": alerta.confianza.value,
                "zona": zona_geom.nombre or zona_geom.distrito,
                "vigencia_inicio": alerta.vigencia_inicio.isoformat()
                if alerta.vigencia_inicio
                else None,
                "vigencia_fin": alerta.vigencia_fin.isoformat() if alerta.vigencia_fin else None,
                "recomendaciones_oficiales": alerta.recomendaciones_oficiales or [],
            }
        )
        fuentes.append(
            {
                "institucion": alerta.entidad_emisora,
                "url": alerta.url_origen,
                "sha256": alerta.sha256_origen,
                "consultada_at": ctx.ahora.isoformat(),
                "confianza": alerta.confianza.value,
            }
        )

    return ToolResult(ok=True, datos={"zona": zona, "alertas": alertas}, fuentes=fuentes)


# ── 2. consultar_perfil_hogar(usuario) ─────────────────────────────────────
@herramienta(
    "consultar_perfil_hogar",
    "Devuelve el perfil del hogar del usuario autenticado: cuántas personas, "
    "si hay adultos mayores, niños, movilidad reducida, mascotas y vehículo.",
    SinArgs,
    Permission.CONFIGURAR_HOGAR,
)
def consultar_perfil_hogar(ctx: ToolContext, _: SinArgs) -> ToolResult:
    """El usuario sale del token, nunca de los argumentos.

    Si el modelo pudiera nombrar al usuario, esta herramienta sería una fuga
    del dato más sensible del sistema (§13.2). Por eso `SinArgs`.
    """
    if ctx.user is None:
        return ToolResult(ok=False, ausencia="No hay usuario autenticado.")

    perfil = ctx.session.scalar(
        select(HouseholdProfile).where(HouseholdProfile.user_id == ctx.user.id)
    )
    if perfil is None:
        return ToolResult(
            ok=True,
            datos={"tiene_perfil": False},
            ausencia=(
                "Este usuario no configuró su perfil del hogar. El perfil es opcional: "
                "da recomendaciones generales, no personalizadas."
            ),
        )

    # Se entrega cantidad y condición. Nunca nombres ni detalle clínico (§13.2).
    return ToolResult(
        ok=True,
        datos={
            "tiene_perfil": True,
            "distrito": perfil.distrito,
            "zona_aproximada": perfil.zona_aproximada,
            "integrantes": perfil.integrantes,
            "ninos": perfil.ninos,
            "adultos_mayores": perfil.adultos_mayores,
            "movilidad_reducida": perfil.movilidad_reducida,
            "discapacidad": perfil.discapacidad,
            "mascotas": perfil.mascotas,
            "vehiculo": perfil.vehiculo,
            "medicamentos_habituales": perfil.medicamentos_habituales,
            "punto_reunion_configurado": perfil.punto_reunion_configurado,
            "mochila_lista": perfil.mochila_lista,
        },
    )


# ── 3. buscar_recursos_cercanos(ubicacion, tipo) ───────────────────────────
# Quien nombra un hospital lo hace a sabiendas y puede estar lejos: Rebagliati
# queda a 7,7 km de Surco, muy fuera de los 3 km por defecto. Buscar por nombre
# dentro del radio de "lo que tengo al lado" es no buscar.
RADIO_BUSQUEDA_POR_NOMBRE_M = 50000.0
TIPOS_SALUD = ("centro_salud", "hospital_publico", "hospital_privado")
TIPOS_HOSPITAL = ("hospital_cualquiera", "hospital_publico", "hospital_privado")


@herramienta(
    "buscar_recursos_cercanos",
    "Busca refugios, centros de salud y puntos de apoyo cerca de una ubicación. "
    "Si el usuario nombra un sitio concreto —por ejemplo «el hospital Rebagliati»— "
    "pasa ese nombre en `nombre` para buscar ese y no el más cercano. "
    "Solo devuelve los registrados y validados por el municipio.",
    RecursosArgs,
    Permission.CONSULTAR_ALERTAS,
)
def buscar_recursos_cercanos(ctx: ToolContext, args: RecursosArgs) -> ToolResult:
    punto = from_shape(Point(args.lon, args.lat), srid=SRID)
    condiciones = [
        Resource.disponible.is_(True),
        # §20.2: un destino no validado provoca descarte duro de la ruta.
        # Ofrecerlo aquí solo produciría una ruta que después se descarta.
        Resource.validado.is_(True),
    ]
    if args.nombre:
        # El nombre manda sobre el tipo. Si alguien dice "Rebagliati" y el
        # modelo dedujo `refugio`, exigir las dos cosas no encuentra nada y la
        # respuesta acaba siendo la lista de al lado, que es el fallo que esto
        # corrige. El nombre ya es una señal suficientemente concreta.
        condiciones.append(Resource.nombre.ilike(f"%{args.nombre}%"))
        radio = max(args.radio_m, RADIO_BUSQUEDA_POR_NOMBRE_M)
    else:
        if args.tipo == "hospital_cualquiera":
            # La petición «cualquier hospital» no se limita a 3 km: se busca
            # el más cercano entre todos los hospitales disponibles y
            # validados que existan en el registro municipal.
            condiciones.append(Resource.tipo.in_(TIPOS_SALUD))
            radio = None
        else:
            condiciones.append(Resource.tipo == args.tipo)
            # Para hospitales públicos/privados tampoco se debe afirmar que
            # no existen solo porque estén fuera del radio de interfaz.
            radio = None if args.tipo in TIPOS_HOSPITAL else args.radio_m
    if radio is not None:
        condiciones.append(
            func.ST_DWithin(Resource.geom.cast(GEOGRAPHY), cast(punto, GEOGRAPHY), radio)
        )

    stmt = (
        select(
            Resource,
            func.ST_Distance(
                Resource.geom.cast(GEOGRAPHY), cast(punto, GEOGRAPHY)
            ).label("dist"),
        )
        .where(*condiciones)
        .order_by(text("dist"))
        .limit(5)
    )
    filas = ctx.session.execute(stmt).all()

    if not filas:
        if args.nombre:
            # No se sustituye por el más cercano. Quien pide Rebagliati y
            # recibe otro hospital sin que nadie se lo diga puede acabar
            # conduciendo al sitio equivocado creyendo que va al que pidió.
            fila_cercana = ctx.session.execute(
                select(
                    Resource,
                    func.ST_Distance(
                        Resource.geom.cast(GEOGRAPHY), cast(punto, GEOGRAPHY)
                    ).label("dist"),
                )
                .where(
                    Resource.disponible.is_(True),
                    Resource.validado.is_(True),
                    Resource.tipo.in_(TIPOS_SALUD),
                    func.ST_DWithin(
                        Resource.geom.cast(GEOGRAPHY), cast(punto, GEOGRAPHY), args.radio_m
                    ),
                )
                .order_by(text("dist"))
                .limit(1)
            ).first()
            sugerido = None
            if fila_cercana:
                r, d = fila_cercana
                sugerido = {
                    "id": str(r.id),
                    "nombre": r.nombre,
                    "tipo": r.tipo,
                    "direccion": r.direccion,
                    "distancia_m": round(float(d)),
                    "telefono": r.telefono,
                    "ubicacion_referencial": r.origen_osm,
                    "lat": ctx.session.scalar(select(func.ST_Y(r.geom))),
                    "lon": ctx.session.scalar(select(func.ST_X(r.geom))),
                }
            return ToolResult(
                ok=True,
                datos={"recursos": [], "recurso_sugerido": sugerido} if sugerido else {"recursos": []},
                ausencia=(
                    f"No encuentro ningún sitio registrado que se llame "
                    f"«{args.nombre}» a menos de {radio / 1000:.0f} km. No significa "
                    f"que no exista: significa que no está en el registro."
                ),
            )
        etiqueta = (
            "hospital" if args.tipo == "hospital_cualquiera"
            else args.tipo.replace("_", " ")
        )
        return ToolResult(
            ok=True,
            datos={"recursos": []},
            ausencia=(
                f"No hay {etiqueta} validado registrado en el registro municipal. "
                "No significa que no exista: significa que todavía no está registrado."
            ),
        )

    recursos = [
        {
            "id": str(r.id),
            "nombre": r.nombre,
            "tipo": r.tipo,
            "direccion": r.direccion,
            "distancia_m": round(float(d)),
            "telefono": r.telefono,
            "acepta_mascotas": r.acepta_mascotas,
            "ubicacion_referencial": r.origen_osm,
            "accesible_movilidad_reducida": r.accesible_movilidad_reducida,
            "lat": ctx.session.scalar(select(func.ST_Y(r.geom))),
            "lon": ctx.session.scalar(select(func.ST_X(r.geom))),
        }
        for r, d in filas
    ]

    sugerido = None
    if args.nombre:
        fila_cercana = ctx.session.execute(
            select(
                Resource,
                func.ST_Distance(
                    Resource.geom.cast(GEOGRAPHY), cast(punto, GEOGRAPHY)
                ).label("dist"),
            )
            .where(
                Resource.disponible.is_(True),
                Resource.validado.is_(True),
                Resource.tipo.in_(TIPOS_SALUD),
                func.ST_DWithin(
                    Resource.geom.cast(GEOGRAPHY), cast(punto, GEOGRAPHY), args.radio_m
                ),
            )
            .order_by(text("dist"))
            .limit(1)
        ).first()
        if fila_cercana:
            r, d = fila_cercana
            sugerido = {
                "id": str(r.id),
                "nombre": r.nombre,
                "tipo": r.tipo,
                "direccion": r.direccion,
                "distancia_m": round(float(d)),
                "telefono": r.telefono,
                "ubicacion_referencial": r.origen_osm,
                "lat": ctx.session.scalar(select(func.ST_Y(r.geom))),
                "lon": ctx.session.scalar(select(func.ST_X(r.geom))),
            }

    datos = {"recursos": recursos}
    if sugerido and (not recursos or sugerido["id"] != recursos[0]["id"]):
        datos["recurso_sugerido"] = sugerido

    return ToolResult(
        ok=True,
        datos=datos,
        fuentes=[{"institucion": "Registro municipal de recursos", "confianza": "MUNICIPAL"}],
    )


# ── 4. calcular_ruta(origen, destino, perfil, restricciones) ───────────────
@herramienta(
    "calcular_ruta",
    "Calcula la ruta de menor riesgo entre dos puntos, considerando cierres "
    "confirmados, zonas de peligro, reportes vigentes y el perfil del hogar.",
    RutaArgs,
    Permission.CONSULTAR_RUTAS,
)
def calcular_ruta(ctx: ToolContext, args: RutaArgs) -> ToolResult:
    from app.routing.engine import RouteEngine
    from app.routing.valhalla import ValhallaUnavailable

    perfil = None
    if ctx.user is not None:
        perfil = ctx.session.scalar(
            select(HouseholdProfile).where(HouseholdProfile.user_id == ctx.user.id)
        )
    hogar = (
        HouseholdFacts(
            movilidad_reducida=perfil.movilidad_reducida,
            adultos_mayores=perfil.adultos_mayores,
            ninos=perfil.ninos,
            vehiculo=perfil.vehiculo,
        )
        if perfil
        else HouseholdFacts()
    )

    destino_lat, destino_lon = args.destino_lat, args.destino_lon
    destino_resource_id = None
    nombre_destino = None

    if destino_lat is None or destino_lon is None:
        if not args.hacia_refugio:
            return ToolResult(
                ok=False,
                ausencia=(
                    "Falta el destino. Pregunta a dónde quiere ir, o usa "
                    "hacia_refugio para llevarlo al lugar seguro más cercano."
                ),
            )
        # §20.2: el destino tiene que estar validado o la ruta se descarta.
        punto_origen = from_shape(Point(args.origen_lon, args.origen_lat), srid=SRID)
        condiciones_destino = [
            Resource.validado.is_(True),
            Resource.disponible.is_(True),
            func.ST_DWithin(
                cast(Resource.geom, GEOGRAPHY), cast(punto_origen, GEOGRAPHY), 15000.0
            ),
        ]
        if args.tipo_destino:
            condiciones_destino.append(Resource.tipo == args.tipo_destino)

        fila = ctx.session.execute(
            select(
                Resource,
                func.ST_Y(Resource.geom),
                func.ST_X(Resource.geom),
            )
            .where(*condiciones_destino)
            .order_by(
                # Un refugio antes que un centro de salud, aunque quede más
                # lejos dentro del radio. "Ruta de escape" significa ponerse a
                # salvo, y el más cercano sin este criterio salía un centro de
                # diagnóstico por imágenes: existe, está mapeado y no sirve
                # para refugiarse de un huaico.
                #
                # A igualdad de tipo manda la distancia.
                case((Resource.tipo == "refugio", 0), else_=1)
                if not args.tipo_destino
                else func.ST_Distance(
                    cast(Resource.geom, GEOGRAPHY), cast(punto_origen, GEOGRAPHY)
                ),
                func.ST_Distance(
                    cast(Resource.geom, GEOGRAPHY), cast(punto_origen, GEOGRAPHY)
                ),
            )
            .limit(1)
        ).first()
        if fila is None:
            return ToolResult(
                ok=True,
                datos={"sin_ruta_verificable": True},
                # El texto que ve el usuario lo fija el §20.5 en el
                # orquestador. Esto es solo la traza para auditoría.
                ausencia="sin destino validado a menos de 15 km (§20.2)",
            )
        recurso, destino_lat, destino_lon = fila
        destino_resource_id = recurso.id
        nombre_destino = recurso.nombre

    engine = RouteEngine(ctx.session)
    try:
        resultado = engine.calcular(
            (args.origen_lat, args.origen_lon),
            (destino_lat, destino_lon),
            hogar,
            ctx.ahora,
            distrito=perfil.distrito if perfil else None,
            destino_resource_id=destino_resource_id,
        )
    except ValhallaUnavailable as exc:
        return ToolResult(
            ok=False,
            ausencia=(
                "El motor de rutas no está disponible en este momento, así que no "
                "puedo calcular ninguna ruta. No supongas una."
            ),
            datos={"error": str(exc)},
        )

    if resultado.sin_ruta_verificable:
        return ToolResult(
            ok=True,
            datos={
                "sin_ruta_verificable": True,
                "descartadas": [
                    {"ruta": rid, "motivo": m} for rid, m in resultado.ranking.descartadas
                ],
            },
            fuentes=resultado.fuentes,
            ausencia="No hay ruta verificable. Usa la respuesta fija del §20.5.",
        )

    rec = resultado.ranking.recomendada
    assert rec is not None
    valhalla = resultado.rutas_valhalla[rec.ruta_id]

    return ToolResult(
        ok=True,
        datos={
            "sin_ruta_verificable": False,
            "distancia_m": round(valhalla.distancia_m),
            "duracion_s": round(valhalla.duracion_s),
            "puntaje": round(rec.puntaje, 3),
            "motivo_riesgo": rec.motivo_riesgo_maximo,
            "cobertura_suficiente": resultado.cobertura.suficiente,
            "frase_obligatoria": resultado.cobertura.frase,
            "pasos": [m.instruccion for m in valhalla.maniobras],
            "destino": nombre_destino,
            "destino_lat": destino_lat,
            "destino_lon": destino_lon,
            "origen_lat": args.origen_lat,
            "origen_lon": args.origen_lon,
            "geometria": valhalla.shape,
            # Los cierres que la ruta esquivó, para poder dibujarlos.
            #
            # Sin esto el mapa muestra un rodeo sin explicación, y un rodeo sin
            # explicación se desobedece: quien ve que la ruta lo aleja de su
            # destino evidente supone que el sistema se equivocó y tira por la
            # calle cortada. El §24.1 pide el porqué junto a la instrucción;
            # en un mapa el porqué es el polígono rojo encima de la vía.
            "bloqueos": [
                {
                    "lat": b["lat"],
                    "lon": b["lon"],
                    "radio_m": b["radio_m"],
                    "motivo": b["motivo"],
                    "vinculante": b["vinculante"],
                }
                for b in resultado.bloqueos_dibujables
            ],
            "hay_alternativa": resultado.ranking.alternativa is not None,
            "rutas_descartadas": [
                {"ruta": rid, "motivo": m} for rid, m in resultado.ranking.descartadas
            ],
        },
        fuentes=resultado.fuentes,
    )


# ── 5. crear_plan_familiar(perfil, alerta) ─────────────────────────────────
@herramienta(
    "crear_plan_familiar",
    "Genera el plan familiar a partir de los protocolos configurados y del "
    "perfil del hogar. Devuelve las acciones críticas tal como están escritas.",
    PlanArgs,
    Permission.GENERAR_PLAN,
)
def crear_plan_familiar(ctx: ToolContext, args: PlanArgs) -> ToolResult:
    """§17: las acciones críticas provienen de protocolos del administrador.

    Esta herramienta devuelve el protocolo textual. El modelo solo puede
    reordenarlo y explicarlo, nunca reescribirlo.
    """
    perfil = None
    if ctx.user is not None:
        perfil = ctx.session.scalar(
            select(HouseholdProfile).where(HouseholdProfile.user_id == ctx.user.id)
        )

    tipo = HazardType.INUNDACION
    if args.alert_id:
        alerta = ctx.session.get(Alert, args.alert_id)
        if alerta:
            tipo = alerta.tipo_evento

    protocolo = ctx.session.scalar(
        select(Protocol).where(Protocol.activo.is_(True), Protocol.hazard_type == tipo.value)
    ) or ctx.session.scalar(select(Protocol).where(Protocol.activo.is_(True)))

    if protocolo is None:
        return ToolResult(
            ok=False,
            ausencia=(
                "No hay protocolo configurado para este tipo de evento. "
                "No inventes acciones críticas."
            ),
        )

    return ToolResult(
        ok=True,
        datos={
            "protocolo": protocolo.codigo,
            "protocolo_version": protocolo.version,
            "entidad": protocolo.entidad,
            "acciones": protocolo.acciones,
            "horizonte_horas": args.horizonte_horas,
            "perfil": {
                "adultos_mayores": perfil.adultos_mayores if perfil else 0,
                "ninos": perfil.ninos if perfil else 0,
                "movilidad_reducida": perfil.movilidad_reducida if perfil else False,
                "mascotas": perfil.mascotas if perfil else 0,
                "medicamentos_habituales": perfil.medicamentos_habituales if perfil else False,
                "vehiculo": perfil.vehiculo if perfil else False,
            },
        },
        fuentes=[
            {
                "institucion": protocolo.entidad or "Protocolo configurado",
                "consultada_at": ctx.ahora.isoformat(),
                "confianza": ConfidenceLevel.OFICIAL.value,
            }
        ],
    )


# ── 6. consultar_reporte(via) ──────────────────────────────────────────────
@herramienta(
    "consultar_reporte",
    "Consulta reportes ciudadanos y cierres registrados sobre una vía. "
    "Distingue siempre lo oficial de lo ciudadano.",
    ReporteArgs,
    Permission.CONSULTAR_ALERTAS,
)
def consultar_reporte(ctx: ToolContext, args: ReporteArgs) -> ToolResult:
    """§12 y §19: lo oficial y lo ciudadano se devuelven en listas separadas.

    Mezclarlos en una sola lista es lo que el §25 prohíbe explícitamente, y una
    vez mezclados el modelo ya no puede volver a separarlos.
    """
    via = args.via.strip().lower()

    cierres = list(
        ctx.session.scalars(
            select(RoadBlock).where(
                func.lower(RoadBlock.nombre_via).contains(via),
                RoadBlock.vigente.is_(True),
                RoadBlock.reabierto_at.is_(None),
            )
        )
    )
    reportes = list(
        ctx.session.scalars(
            select(CitizenReport).where(
                func.lower(func.coalesce(CitizenReport.direccion_aproximada, "")).contains(via),
                or_(CitizenReport.vence_at.is_(None), CitizenReport.vence_at >= ctx.ahora),
                CitizenReport.estado.notin_(["rechazado", "duplicado", "borrador"]),
            )
        )
    )

    if not cierres and not reportes:
        return ToolResult(
            ok=True,
            datos={"cierres_oficiales": [], "reportes_ciudadanos": []},
            ausencia=(
                f"No hay cierre ni reporte registrado para «{args.via}». "
                f"No hay información suficiente para confirmar que esa vía sea transitable."
            ),
        )

    return ToolResult(
        ok=True,
        datos={
            "cierres_oficiales": [
                {
                    "via": c.nombre_via,
                    "motivo": c.motivo.value,
                    "confianza": c.confianza.value,
                    "desde": c.inicio_at.isoformat() if c.inicio_at else None,
                    "vinculante": c.es_vinculante(),
                }
                for c in cierres
            ],
            "reportes_ciudadanos": [
                {
                    "tipo": r.tipo.value,
                    "estado": r.estado.value,
                    "confianza": r.trust_level.value,
                    "reportado_at": r.reportado_at.isoformat(),
                    "validado": r.trust_level
                    in (TrustLevel.VALIDADO, TrustLevel.CONFIRMADO),
                }
                for r in reportes
            ],
        },
        fuentes=[
            {"institucion": "Registro municipal de cierres", "confianza": "MUNICIPAL"}
            if cierres
            else {"institucion": "Reportes ciudadanos", "confianza": "SIN_CONFIRMAR"}
        ],
    )


# ── 7. consultar_estado_fuentes() ──────────────────────────────────────────
@herramienta(
    "consultar_estado_fuentes",
    "Devuelve qué fuentes oficiales están respondiendo y cuáles no. "
    "Úsala cuando no encuentres información, para poder declarar la ausencia.",
    SinArgs,
    Permission.CONSULTAR_ALERTAS,
)
def consultar_estado_fuentes(ctx: ToolContext, _: SinArgs) -> ToolResult:
    from app.sources.registry import POR_TEMA

    fuentes = list(ctx.session.scalars(select(OfficialSource).where(OfficialSource.activa.is_(True))))
    categorias_por_slug: dict[str, list[str]] = {f.slug: [] for f in fuentes}
    for categoria, definiciones in POR_TEMA.items():
        for definicion in definiciones:
            if definicion in categorias_por_slug:
                categorias_por_slug[definicion].append(categoria.value)
    estados = [
        {
            "slug": f.slug,
            "institucion": f.institucion,
            "categorias": categorias_por_slug.get(f.slug, []),
            "url": f.url,
            "tipo_informacion": f.tipo_informacion,
            "vigencia_horas": f.vigencia_horas,
            "estado": f.ultimo_estado.value,
            "verificada": f.verificada,
            "ultima_consulta": f.ultima_consulta_at.isoformat() if f.ultima_consulta_at else None,
            "citable": f.puede_citarse_como_vigente(ctx.ahora),
            "declaracion": declarar_ausencia(f.institucion, f.ultimo_estado),
        }
        for f in fuentes
    ]
    caidas = [e for e in estados if e["estado"] in ("caido", "obsoleto")]
    return ToolResult(
        ok=True,
        datos={
            "fuentes": estados,
            "catalogo_por_categoria": {
                categoria.value: [
                    {
                        "slug": definicion,
                        "institucion": next((f["institucion"] for f in estados if f["slug"] == definicion), definicion),
                        "url": next((f["url"] for f in estados if f["slug"] == definicion), None),
                    }
                    for definicion in definiciones
                ]
                for categoria, definiciones in POR_TEMA.items()
            },
            "hay_fuentes_caidas": bool(caidas),
        },
        ausencia=(
            "Hay fuentes oficiales sin responder. Decláralo: no presentes el "
            "silencio como ausencia de peligro."
            if caidas
            else None
        ),
    )


# ── 8. consultar_web_oficial(url) ──────────────────────────────────────────
@herramienta(
    "consultar_web_oficial",
    "Consulta una URL HTTPS de una fuente oficial registrada en SENTI. Úsala "
    "solo para obtener información actual de SENAMHI, INDECI, IGP, SUTRAN, "
    "INGEMMET u otra fuente oficial ya registrada.",
    WebOficialArgs,
    Permission.CONSULTAR_ALERTAS,
)
def consultar_web_oficial(ctx: ToolContext, args: WebOficialArgs) -> ToolResult:
    parsed = urlparse(args.url)
    dominio = _dominio_de(args.url).removeprefix("www.")
    dominios_permitidos = _dominios_oficiales(ctx)

    if parsed.scheme != "https":
        return ToolResult(
            ok=False,
            ausencia="Solo se permiten URLs HTTPS de fuentes oficiales registradas.",
        )
    if not _dominio_publico_permitido(dominio):
        return ToolResult(ok=False, ausencia="Dominio no público o no permitido.")
    if not _dominio_autorizado(dominio, dominios_permitidos):
        return ToolResult(
            ok=False,
            ausencia=(
                "La URL no pertenece a una fuente oficial registrada en SENTI. "
                "No uses esa página como fuente."
            ),
        )

    try:
        with httpx.Client(
            timeout=WEB_TIMEOUT_S,
            follow_redirects=True,
            headers={"User-Agent": "SENTI/0.1 (gestion de emergencias)"},
        ) as client:
            respuesta = client.get(args.url)
            respuesta.raise_for_status()
    except httpx.HTTPError as exc:
        return ToolResult(
            ok=False,
            datos={"error": str(exc)},
            ausencia="No se pudo consultar la fuente oficial en este momento.",
        )

    final_url = str(respuesta.url)
    dominio_final = _dominio_de(final_url).removeprefix("www.")
    if not _dominio_autorizado(dominio_final, dominios_permitidos):
        return ToolResult(
            ok=False,
            ausencia="La fuente redirigió a un dominio no registrado; no se usa.",
        )

    contenido = respuesta.content[:WEB_MAX_BYTES]
    texto = _texto_visible(contenido, respuesta.headers.get("content-type", ""))
    if not texto:
        return ToolResult(
            ok=False,
            ausencia="La fuente oficial respondió, pero no entregó texto legible.",
        )

    fuente = ctx.session.scalar(
        select(OfficialSource).where(
            OfficialSource.activa.is_(True),
            or_(
                OfficialSource.url.contains(dominio_final),
                OfficialSource.healthcheck_url.contains(dominio_final),
            ),
        )
    )
    institucion = fuente.institucion if fuente else dominio_final

    return ToolResult(
        ok=True,
        datos={
            "url": final_url,
            "http_status": respuesta.status_code,
            "texto": texto,
            "recortado": len(respuesta.content) > len(contenido) or len(texto) >= WEB_MAX_CHARS,
            "instruccion": "Redacta solo con este contenido; no inventes datos faltantes.",
        },
        fuentes=[
            {
                "institucion": institucion,
                "url": final_url,
                "consultada_at": ctx.ahora.isoformat(),
                "confianza": ConfidenceLevel.OFICIAL.value,
            }
        ],
    )


# ── 9. preparar_mensaje_contacto(contexto) ─────────────────────────────────
@herramienta(
    "preparar_mensaje_contacto",
    "Prepara un mensaje corto que el usuario pueda enviar a su contacto de "
    "confianza. Devuelve el borrador; el usuario decide si lo envía.",
    MensajeContactoArgs,
    Permission.USAR_CHAT,
)
def preparar_mensaje_contacto(ctx: ToolContext, args: MensajeContactoArgs) -> ToolResult:
    """§13.2: el contacto de confianza «nunca se usa para enviarle nada sin
    acción del titular».

    Por eso esta herramienta prepara un borrador y no envía nada, y no devuelve
    el teléfono del contacto: el titular ya lo conoce y el modelo no tiene por
    qué verlo.
    """
    perfil = None
    if ctx.user is not None:
        perfil = ctx.session.scalar(
            select(HouseholdProfile).where(HouseholdProfile.user_id == ctx.user.id)
        )

    return ToolResult(
        ok=True,
        datos={
            "tiene_contacto_configurado": bool(
                perfil and perfil.contacto_confianza_telefono_cifrado
            ),
            "contexto": args.contexto,
            "punto_reunion": perfil.punto_reunion_descripcion if perfil else None,
            "solo_borrador": True,
            "nota": (
                "SENTI no envía este mensaje. Se lo entrega al usuario para que "
                "él decida."
            ),
        },
    )


# ── 10. guardar_informacion_offline(datos) ─────────────────────────────────
@herramienta(
    "guardar_informacion_offline",
    "Prepara el paquete que el usuario conservará sin conexión: plan, "
    "checklist, ruta guardada, teléfonos y última alerta con su fecha.",
    OfflineArgs,
    Permission.USAR_CHAT,
)
def guardar_informacion_offline(ctx: ToolContext, args: OfflineArgs) -> ToolResult:
    """§26. Lo que se guarda lleva SIEMPRE su fecha.

    "No presenta una alerta antigua como vigente": por eso cada bloque va con
    `sincronizado_at` y el cliente muestra esa fecha, no la hora actual.
    """
    region = phones.REGION_NACIONAL
    perfil = None
    if ctx.user is not None:
        perfil = ctx.session.scalar(
            select(HouseholdProfile).where(HouseholdProfile.user_id == ctx.user.id)
        )
    if perfil and perfil.distrito:
        db_region = ctx.session.scalar(
            select(EmergencyPhone.region).where(EmergencyPhone.region.contains(perfil.distrito))
        )
        region = db_region or region

    paquete: dict = {"sincronizado_at": ctx.ahora.isoformat()}

    if args.incluir_telefonos:
        paquete["telefonos"] = [
            {"situacion": c.situacion, "numero": c.numero, "entidad": c.entidad}
            for c in phones.para_region(region)
        ]
    if args.incluir_plan:
        paquete["incluye_plan"] = True
    if args.incluir_ruta:
        paquete["incluye_ultima_ruta"] = True

    paquete["instruccion_sin_senal"] = True
    paquete["no_disponible_offline"] = [
        "alertas nuevas",
        "estado de vías en tiempo real",
        "nuevos reportes",
        "confirmaciones municipales",
        "recálculo con datos externos recientes",
    ]

    return ToolResult(ok=True, datos=paquete)
