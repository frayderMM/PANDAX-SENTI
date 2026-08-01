"""Política de retención (§13.5) y base legal (§13.3).

El DS 016-2024-JUS exige minimización y plazos de conservación demostrables
(§13.1). Estos plazos no son configurables por conveniencia operativa: están
declarados en el aviso de consentimiento del §13.4 ("la borro en 72 h", "la
borro en 30 días"), y cambiarlos sin volver a pedir consentimiento rompe el
propio consentimiento.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime, timedelta


class RetentionPolicy(str, enum.Enum):
    UBICACION_EXACTA = "ubicacion_exacta"
    UBICACION_DISTRITO = "ubicacion_distrito"
    FOTOGRAFIA_REPORTE = "fotografia_reporte"
    MENSAJES = "mensajes"
    PERFIL_HOGAR = "perfil_hogar"
    TELEFONO = "telefono"
    AUDITORIA = "auditoria"


# §13.5, literal. `None` = "mientras exista la cuenta" o "no aplica plazo".
PLAZOS: dict[RetentionPolicy, timedelta | None] = {
    RetentionPolicy.UBICACION_EXACTA: timedelta(hours=72),
    RetentionPolicy.UBICACION_DISTRITO: timedelta(days=365),
    RetentionPolicy.FOTOGRAFIA_REPORTE: timedelta(days=30),
    RetentionPolicy.MENSAJES: timedelta(days=365),
    # Mientras exista la cuenta; borrado a solicitud.
    RetentionPolicy.PERFIL_HOGAR: None,
    # Seudonimizado con hash: no es un plazo, es una transformación al ingreso.
    RetentionPolicy.TELEFONO: None,
    RetentionPolicy.AUDITORIA: timedelta(days=730),
}

DESCRIPCION: dict[RetentionPolicy, str] = {
    RetentionPolicy.UBICACION_EXACTA: "Ubicación exacta: 72 horas",
    RetentionPolicy.UBICACION_DISTRITO: "Ubicación reducida a distrito: 12 meses",
    RetentionPolicy.FOTOGRAFIA_REPORTE: (
        "Fotografía de reporte: 30 días, o hasta la resolución del incidente si es menor"
    ),
    RetentionPolicy.MENSAJES: "Texto de mensajes y conversación: 12 meses",
    RetentionPolicy.PERFIL_HOGAR: (
        "Perfil del hogar: mientras exista la cuenta, borrado a solicitud"
    ),
    RetentionPolicy.TELEFONO: "Número de teléfono: seudonimizado con hash",
    RetentionPolicy.AUDITORIA: "Log de auditoría: 24 meses",
}


def expira_en(politica: RetentionPolicy, desde: datetime) -> datetime | None:
    plazo = PLAZOS[politica]
    return None if plazo is None else desde + plazo


def expira_foto(reportado_at: datetime, resuelto_at: datetime | None = None) -> datetime:
    """§13.5: 30 días, **o hasta la resolución del incidente si es menor**.

    La resolución adelanta el borrado, nunca lo retrasa. Un incidente que sigue
    abierto a los 40 días no conserva la foto: el plazo máximo manda.
    """
    limite = reportado_at + PLAZOS[RetentionPolicy.FOTOGRAFIA_REPORTE]
    if resuelto_at is not None and resuelto_at < limite:
        return resuelto_at
    return limite


@dataclass(frozen=True)
class AvisoRetencion:
    """Lo que se le dice al titular sobre sus datos (§13.4, comando MIS DATOS)."""

    lineas: tuple[str, ...]

    @classmethod
    def completo(cls) -> AvisoRetencion:
        return cls(tuple(DESCRIPCION[p] for p in RetentionPolicy))

    def render(self) -> str:
        cabecera = "Esto es lo que guardo y hasta cuándo:"
        cuerpo = "\n".join(f"· {linea}" for linea in self.lineas)
        pie = (
            "Ninguna imagen ni conversación se usa para entrenar modelos. "
            "Escribe BORRAR para eliminar un incidente y sus adjuntos."
        )
        return f"{cabecera}\n{cuerpo}\n{pie}"


# §13.6, plan de brecha. Escrito y ensayado antes del piloto.
PLAN_BRECHA = (
    "Detección",
    "Contención",
    "Evaluación de alcance",
    "Notificación a la ANPD dentro de 48 h",
    "Notificación a titulares afectados si hay riesgo alto",
    "Informe post-incidente y rotación de credenciales",
)
PLAZO_NOTIFICACION_ANPD = timedelta(hours=48)
