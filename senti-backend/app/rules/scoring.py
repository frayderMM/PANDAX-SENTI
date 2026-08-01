"""Descarte duro y puntaje de rutas (§20.2, §20.3).

Este módulo es el diferenciador del proyecto (§20) y es donde un error se paga
con una persona enviada a una vía cerrada. Todo aquí es determinista y
probable sin red: recibe hechos ya verificados por PostGIS y Valhalla, y
devuelve un número y su explicación.

Dos mecanismos que no se mezclan (§20.2 vs §20.3):

- **Descarte duro**: la ruta desaparece. No compite, no se puntúa, no se
  muestra "por si acaso". Cierre oficial, puente afectado, quebrada activada,
  cruzar agua, contradecir una orden oficial, destino no validado.
- **Penalización**: la ruta baja de puntaje y puede seguir siendo la mejor
  disponible. Zonas de peligro amplias y reportes comunitarios.

Confundirlos en cualquier dirección rompe el sistema: penalizar un cierre
oficial produce el falso negativo que el §32.2 fija en 0 %; descartar por un
reporte pendiente deja a la persona sin ninguna ruta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.domain import HAZARD_VALIDITY, HazardType, TrustLevel

# ── §20.3, pesos. Suman 1.0; se verifica al importar. ──────────────────────
PESOS: dict[str, float] = {
    "seguridad": 0.50,
    "fuente": 0.20,
    "accesible": 0.15,
    "duracion": 0.10,
    "distancia": 0.05,
}
assert abs(sum(PESOS.values()) - 1.0) < 1e-9, "Los pesos del §20.3 deben sumar 1.0"

# ── §20.3, riesgo por tramo. ───────────────────────────────────────────────
RIESGO_CIERRE_VIGENTE = 1.00  # → descarte, no puntaje
RIESGO_ZONA_PELIGRO_ALTO = 0.70
RIESGO_REPORTE_VALIDADO = 0.55
RIESGO_REPORTE_PROBABLE = 0.40
RIESGO_REPORTE_PENDIENTE = 0.15
RIESGO_SIN_SENAL = 0.00

RIESGO_POR_CONFIANZA: dict[TrustLevel, float] = {
    TrustLevel.VALIDADO: RIESGO_REPORTE_VALIDADO,
    TrustLevel.PROBABLE: RIESGO_REPORTE_PROBABLE,
    TrustLevel.PENDIENTE: RIESGO_REPORTE_PENDIENTE,
}

# §20.3: "reporte ... a menos de 200 m".
RADIO_REPORTE_M = 200.0

# ── §20.3, S_fuente. ───────────────────────────────────────────────────────
S_FUENTE_TODO_OFICIAL = 1.0
S_FUENTE_MIXTO = 0.6
S_FUENTE_SOLO_COMUNITARIO = 0.3
S_FUENTE_SIN_INFORMACION = 0.0


def peso_temporal(
    reportado_at: datetime,
    ahora: datetime,
    tipo: HazardType,
    vigencias: dict[HazardType, timedelta] | None = None,
) -> float:
    """Decaimiento temporal del §20.3.

    "El peso de un reporte comunitario decae linealmente hasta cero al cumplir
    su vigencia por tipo de peligro. Un reporte vencido no penaliza ni
    tranquiliza."

    Devuelve 1.0 recién reportado y 0.0 al cumplirse la vigencia. Que devuelva
    exactamente 0.0 es lo que hace que un reporte vencido "no penalice"; que no
    devuelva un valor negativo ni se convierta en señal de seguridad es lo que
    hace que "tampoco tranquilice".
    """
    vigencia = (vigencias or HAZARD_VALIDITY).get(tipo, HAZARD_VALIDITY[HazardType.OTRO])
    if vigencia.total_seconds() <= 0:
        return 0.0
    transcurrido = (ahora - reportado_at).total_seconds()
    if transcurrido <= 0:
        return 1.0
    restante = 1.0 - (transcurrido / vigencia.total_seconds())
    return max(0.0, min(1.0, restante))


@dataclass(frozen=True)
class ReportRisk:
    """Un reporte comunitario cerca de un tramo."""

    trust_level: TrustLevel
    tipo: HazardType
    reportado_at: datetime
    distancia_m: float


@dataclass(frozen=True)
class SegmentFacts:
    """Hechos ya verificados sobre un tramo. Ninguno lo produce el modelo."""

    cruza_cierre_vigente: bool = False
    intersecta_zona_peligro_alto: bool = False
    reportes_cercanos: tuple[ReportRisk, ...] = ()
    pendiente_max_pct: float = 0.0
    tiene_escaleras: bool = False
    superficie_irregular: bool = False


@dataclass(frozen=True)
class HouseholdFacts:
    """Perfil del hogar reducido a lo que cambia el cálculo (§14)."""

    movilidad_reducida: bool = False
    adultos_mayores: int = 0
    ninos: int = 0
    vehiculo: bool = True


@dataclass(frozen=True)
class RouteFacts:
    """Una ruta candidata devuelta por Valhalla, ya cruzada con PostGIS."""

    id: str
    segmentos: tuple[SegmentFacts, ...]
    distancia_m: float
    duracion_s: float
    # §20.2, condiciones de descarte duro que no son "cruzar un cierre".
    atraviesa_puente_afectado: bool = False
    entra_quebrada_activada: bool = False
    requiere_cruzar_agua: bool = False
    contradice_orden_evacuacion: bool = False
    destino_validado: bool = True
    # §20.3, S_fuente.
    bloqueos_de_fuente_oficial: int = 0
    bloqueos_de_fuente_comunitaria: int = 0
    hay_informacion_reciente_zona: bool = True


@dataclass(frozen=True)
class RouteScore:
    ruta_id: str
    s_seguridad: float
    s_fuente: float
    s_accesible: float
    s_duracion: float
    s_distancia: float
    puntaje: float
    riesgo_maximo: float
    motivo_riesgo_maximo: str
    detalle: dict[str, float] = field(default_factory=dict)


# ── §20.2, descarte duro ───────────────────────────────────────────────────
def motivo_descarte(ruta: RouteFacts) -> str | None:
    """Devuelve el motivo si la ruta se descarta, o None si sobrevive (§20.2).

    El orden de las comprobaciones sigue el del documento. Cualquiera basta.
    """
    if ruta.contradice_orden_evacuacion:
        return "contradice una orden oficial de evacuación"
    if any(s.cruza_cierre_vigente for s in ruta.segmentos):
        return "cruza un cierre oficial o municipal vigente"
    if ruta.atraviesa_puente_afectado:
        return "atraviesa un puente reportado como afectado"
    if ruta.entra_quebrada_activada:
        return "entra a una quebrada con activación reportada"
    if ruta.requiere_cruzar_agua:
        return "requiere cruzar agua"
    if not ruta.destino_validado:
        return "conduce a un destino no validado"
    return None


# ── §20.3, subpuntajes ─────────────────────────────────────────────────────
def riesgo_segmento(
    seg: SegmentFacts,
    ahora: datetime,
    vigencias: dict[HazardType, timedelta] | None = None,
) -> tuple[float, str]:
    """Riesgo de un tramo y el motivo del valor devuelto.

    Gana el riesgo más alto: el §20.3 define `S_seguridad` sobre el máximo, no
    sobre una suma. Dos señales medias no equivalen a una grave.
    """
    candidatos: list[tuple[float, str]] = [(RIESGO_SIN_SENAL, "sin señal de riesgo")]

    if seg.cruza_cierre_vigente:
        # No debería llegar aquí: el descarte duro corre antes. Se deja por si
        # alguien puntúa un tramo sin haber descartado, para que no puntúe bajo.
        candidatos.append((RIESGO_CIERRE_VIGENTE, "cierre oficial o municipal vigente"))

    if seg.intersecta_zona_peligro_alto:
        candidatos.append(
            (RIESGO_ZONA_PELIGRO_ALTO, "zona de peligro alto intersectada (INGEMMET / SIGRID / ANA)")
        )

    for r in seg.reportes_cercanos:
        if r.distancia_m > RADIO_REPORTE_M:
            continue
        base = RIESGO_POR_CONFIANZA.get(r.trust_level)
        if base is None:
            continue
        peso = peso_temporal(r.reportado_at, ahora, r.tipo, vigencias)
        # Un reporte vencido aporta 0.0 y por tanto nunca gana el máximo.
        candidatos.append(
            (base * peso, f"reporte {r.trust_level.value} a menos de {RADIO_REPORTE_M:.0f} m")
        )

    return max(candidatos, key=lambda c: c[0])


def s_seguridad(
    ruta: RouteFacts,
    ahora: datetime,
    vigencias: dict[HazardType, timedelta] | None = None,
) -> tuple[float, float, str]:
    """`S_seguridad = 1 − max(riesgo de cualquier tramo)` (§20.3)."""
    if not ruta.segmentos:
        return 1.0, 0.0, "sin señal de riesgo"
    riesgos = [riesgo_segmento(s, ahora, vigencias) for s in ruta.segmentos]
    riesgo_max, motivo = max(riesgos, key=lambda r: r[0])
    return 1.0 - riesgo_max, riesgo_max, motivo


def s_fuente(ruta: RouteFacts) -> float:
    """§20.3, calidad de la fuente de los bloqueos considerados."""
    oficial = ruta.bloqueos_de_fuente_oficial
    comunitario = ruta.bloqueos_de_fuente_comunitaria
    if not ruta.hay_informacion_reciente_zona:
        return S_FUENTE_SIN_INFORMACION
    if oficial and comunitario:
        return S_FUENTE_MIXTO
    if oficial:
        return S_FUENTE_TODO_OFICIAL
    if comunitario:
        return S_FUENTE_SOLO_COMUNITARIO
    # Hay información reciente de la zona y no hay bloqueo que considerar: la
    # información disponible es oficial y dice que no hay nada.
    return S_FUENTE_TODO_OFICIAL


def s_accesible(ruta: RouteFacts, hogar: HouseholdFacts) -> float:
    """§20.3: `1 − penalización por pendiente, escaleras y superficie`,
    ponderada por el perfil del hogar.

    "Sin condiciones especiales, S_accesible = 1": si el hogar no declara nada
    y va en vehículo, la pendiente y las escaleras no penalizan, porque no le
    afectan.
    """
    sensibilidad = 0.0
    if hogar.movilidad_reducida:
        sensibilidad = max(sensibilidad, 1.0)
    if hogar.adultos_mayores > 0:
        sensibilidad = max(sensibilidad, 0.6)
    if hogar.ninos > 0:
        sensibilidad = max(sensibilidad, 0.3)
    if not hogar.vehiculo:
        sensibilidad = max(sensibilidad, 0.3)

    if sensibilidad == 0.0:
        return 1.0

    pendiente_max = max((s.pendiente_max_pct for s in ruta.segmentos), default=0.0)
    hay_escaleras = any(s.tiene_escaleras for s in ruta.segmentos)
    hay_superficie_mala = any(s.superficie_irregular for s in ruta.segmentos)

    # Una pendiente del 8 % ya es el límite de accesibilidad en normativa
    # peatonal; a 15 % se considera intransitable con silla de ruedas.
    pen_pendiente = min(1.0, max(0.0, (pendiente_max - 4.0) / 11.0)) * 0.5
    pen_escaleras = 0.4 if hay_escaleras else 0.0
    pen_superficie = 0.2 if hay_superficie_mala else 0.0

    penalizacion = min(1.0, (pen_pendiente + pen_escaleras + pen_superficie) * sensibilidad)
    return max(0.0, 1.0 - penalizacion)


def _s_relativo(valor: float, minimo: float) -> float:
    """`1 − (valor − mínimo) / mínimo`, acotado a [0,1] (§20.3).

    La ruta más corta obtiene 1.0. Una que dobla el mínimo obtiene 0.0.
    """
    if minimo <= 0:
        return 1.0
    return max(0.0, min(1.0, 1.0 - (valor - minimo) / minimo))


def puntuar(
    ruta: RouteFacts,
    hogar: HouseholdFacts,
    ahora: datetime,
    *,
    duracion_minima_s: float,
    distancia_minima_m: float,
    pesos: dict[str, float] | None = None,
    vigencias: dict[HazardType, timedelta] | None = None,
) -> RouteScore:
    """Puntaje del §20.3. La ruta ya debe haber pasado el descarte duro."""
    w = pesos or PESOS
    seg, riesgo_max, motivo = s_seguridad(ruta, ahora, vigencias)
    fue = s_fuente(ruta)
    acc = s_accesible(ruta, hogar)
    dur = _s_relativo(ruta.duracion_s, duracion_minima_s)
    dis = _s_relativo(ruta.distancia_m, distancia_minima_m)

    total = (
        w["seguridad"] * seg
        + w["fuente"] * fue
        + w["accesible"] * acc
        + w["duracion"] * dur
        + w["distancia"] * dis
    )

    return RouteScore(
        ruta_id=ruta.id,
        s_seguridad=seg,
        s_fuente=fue,
        s_accesible=acc,
        s_duracion=dur,
        s_distancia=dis,
        puntaje=total,
        riesgo_maximo=riesgo_max,
        motivo_riesgo_maximo=motivo,
        detalle=dict(w),
    )


@dataclass(frozen=True)
class RankingResult:
    recomendada: RouteScore | None
    alternativa: RouteScore | None
    descartadas: tuple[tuple[str, str], ...]  # (ruta_id, motivo)

    @property
    def sin_ruta_verificable(self) -> bool:
        """§20.2: si todas se descartan, el resultado es `sin ruta verificable`,
        sin excepción."""
        return self.recomendada is None


def rankear(
    rutas: list[RouteFacts],
    hogar: HouseholdFacts,
    ahora: datetime,
    *,
    pesos: dict[str, float] | None = None,
    vigencias: dict[HazardType, timedelta] | None = None,
) -> RankingResult:
    """Descarta, puntúa y ordena (§20.1 → §20.3).

    Devuelve ruta recomendada y alternativa. Si no sobrevive ninguna, devuelve
    `sin_ruta_verificable`, que el §20.2 exige "sin excepción": no se degrada a
    "la menos mala".
    """
    descartadas: list[tuple[str, str]] = []
    supervivientes: list[RouteFacts] = []
    for r in rutas:
        motivo = motivo_descarte(r)
        if motivo:
            descartadas.append((r.id, motivo))
        else:
            supervivientes.append(r)

    if not supervivientes:
        return RankingResult(None, None, tuple(descartadas))

    # Los mínimos se calculan sobre las supervivientes: comparar contra una
    # ruta descartada por cruzar un cierre falsearía S_duracion y S_distancia.
    dur_min = min(r.duracion_s for r in supervivientes)
    dis_min = min(r.distancia_m for r in supervivientes)

    puntajes = sorted(
        (
            puntuar(
                r,
                hogar,
                ahora,
                duracion_minima_s=dur_min,
                distancia_minima_m=dis_min,
                pesos=pesos,
                vigencias=vigencias,
            )
            for r in supervivientes
        ),
        key=lambda s: s.puntaje,
        reverse=True,
    )

    return RankingResult(
        recomendada=puntajes[0],
        alternativa=puntajes[1] if len(puntajes) > 1 else None,
        descartadas=tuple(descartadas),
    )
