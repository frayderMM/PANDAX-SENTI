"""Escalera de confianza de reportes ciudadanos (§21.2).

    | Nivel      | Cómo se alcanza                                    | Efecto      |
    | pendiente  | un reporte individual                              | pen. baja   |
    | probable   | dos reportes independientes <300 m en <60 min      | pen. media  |
    | validado   | decisión de un validador con evidencia             | pen. alta   |
    | confirmado | operador municipal o fuente oficial                | EXCLUSIÓN   |

"Una fotografía no cierra una vía. La heurística eleva a probable; solo una
persona con rol eleva a validado; solo el municipio o el Estado cierran."
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domain import ConfidenceLevel, TrustLevel

# §21.2, literales.
RADIO_COINCIDENCIA_M = 300.0
VENTANA_COINCIDENCIA = timedelta(minutes=60)
REPORTES_PARA_PROBABLE = 2

_RADIO_TIERRA_M = 6_371_000.0


def distancia_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine, en metros.

    En producción esta distancia la calcula PostGIS con `ST_DWithin` sobre
    geography. Aquí está en Python puro a propósito: la escalera de confianza
    tiene que poder probarse sin levantar una base de datos.
    """
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * _RADIO_TIERRA_M * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class ReportSignal:
    """Lo mínimo de un reporte que necesita la escalera de confianza."""

    reporter_id: str | None
    lat: float
    lon: float
    reportado_at: datetime


@dataclass(frozen=True)
class TrustDecision:
    nivel: TrustLevel
    motivo: str
    reportes_coincidentes: int = 0

    @property
    def excluye_de_ruta(self) -> bool:
        """§21.2: solo `confirmado` excluye. El resto penaliza."""
        return self.nivel is TrustLevel.CONFIRMADO


def _independientes(base: ReportSignal, otros: list[ReportSignal]) -> list[ReportSignal]:
    """Filtra los que cuentan para la heurística de "dos reportes independientes".

    Independiente significa **de otra persona**. Sin este filtro, alguien que
    envía el mismo reporte dos veces eleva su propio reporte a probable, y a
    partir de ahí penaliza rutas reales de otras personas. Un reporte sin autor
    identificado no puede probarse independiente, así que no cuenta.
    """
    vistos: set[str] = set()
    resultado: list[ReportSignal] = []
    for o in otros:
        if o.reporter_id is None or o.reporter_id == base.reporter_id:
            continue
        if o.reporter_id in vistos:
            continue
        if abs(o.reportado_at - base.reportado_at) > VENTANA_COINCIDENCIA:
            continue
        if distancia_m(base.lat, base.lon, o.lat, o.lon) > RADIO_COINCIDENCIA_M:
            continue
        vistos.add(o.reporter_id)
        resultado.append(o)
    return resultado


def evaluar(
    base: ReportSignal,
    otros_reportes: list[ReportSignal] | None = None,
    *,
    validado_por_validador: bool = False,
    tiene_evidencia: bool = False,
    confirmado_por: ConfidenceLevel | None = None,
) -> TrustDecision:
    """Calcula el nivel de confianza del §21.2.

    Se evalúa de mayor a menor: una confirmación municipal no se degrada
    porque además existan reportes ciudadanos.
    """
    # Confirmado: solo municipio o fuente oficial (§6, §21.2).
    if confirmado_por in (ConfidenceLevel.OFICIAL, ConfidenceLevel.MUNICIPAL):
        return TrustDecision(
            TrustLevel.CONFIRMADO,
            f"confirmado por fuente {confirmado_por.value.lower()}",
        )

    # Validado: decisión de un validador CON evidencia. Sin evidencia no sube:
    # el §21.2 dice "decisión de un validador con evidencia", no "decisión de
    # un validador".
    if validado_por_validador and tiene_evidencia:
        return TrustDecision(TrustLevel.VALIDADO, "validado con evidencia")

    coincidentes = _independientes(base, otros_reportes or [])
    if len(coincidentes) + 1 >= REPORTES_PARA_PROBABLE:
        return TrustDecision(
            TrustLevel.PROBABLE,
            f"{len(coincidentes) + 1} reportes independientes a menos de "
            f"{RADIO_COINCIDENCIA_M:.0f} m dentro de "
            f"{int(VENTANA_COINCIDENCIA.total_seconds() // 60)} minutos",
            reportes_coincidentes=len(coincidentes) + 1,
        )

    return TrustDecision(TrustLevel.PENDIENTE, "reporte individual", reportes_coincidentes=1)
