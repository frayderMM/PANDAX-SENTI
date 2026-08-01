"""Indicadores derivados del panel municipal (§22).

Todo lo que hay aquí es una clasificación determinista de datos que ya vienen
de la base de datos — sin heurística de texto ni modelo de por medio. Vive en
`app/rules/`, no en el router, porque tiene que poder probarse sin levantar
una base de datos, igual que el resto de las reglas duras del §32.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain import HazardType, ReportState

# Perú (INDECI/SENAMHI) usa Verde/Amarilla/Naranja/Roja. Este dashboard solo
# distingue tres colores de badge; Naranja se trata como crítica igual que
# Roja porque ambas exigen la misma respuesta inmediata del operador.
_NIVELES_CRITICOS = {"roja", "rojo", "naranja"}
_NIVELES_MODERADOS = {"amarilla", "amarillo"}


def color_alerta(nivel_oficial: str | None) -> str:
    """Reduce el nivel oficial (texto libre, p. ej. "Naranja") a un color de badge.

    Sin nivel oficial se trata como el caso más grave: una alerta vigente sin
    clasificar no debe verse más tranquila en el tablero que una que sí la
    tiene.
    """
    valor = (nivel_oficial or "").strip().lower()
    if not valor or valor in _NIVELES_CRITICOS:
        return "roja"
    if valor in _NIVELES_MODERADOS:
        return "amarilla"
    return "verde"


def es_alerta_critica(nivel_oficial: str | None) -> bool:
    return color_alerta(nivel_oficial) == "roja"


def estado_incidencia(estado: ReportState) -> str:
    """Lo que ve el operador: sigue abierto, o ya se resolvió.

    Los matices internos del §21.1 (pendiente/en_revision/confirmado) son la
    misma cosa para esta vista — "en proceso" — porque en ningún caso el
    reporte está cerrado todavía.
    """
    return "Atendida" if estado is ReportState.RESUELTO else "En proceso"


_TEXTO_TIPO_PELIGRO: dict[HazardType, str] = {
    HazardType.INUNDACION: "Inundación",
    HazardType.HUAICO: "Huaico",
    HazardType.DESLIZAMIENTO: "Deslizamiento",
    HazardType.LLUVIA: "Lluvia intensa",
    HazardType.SISMO: "Sismo",
    HazardType.TSUNAMI: "Tsunami",
    HazardType.INCENDIO: "Incendio",
    HazardType.VIA_BLOQUEADA: "Vía bloqueada",
    HazardType.PUENTE_AFECTADO: "Puente afectado",
    HazardType.ACUMULACION_AGUA: "Acumulación de agua",
}


def texto_tipo_peligro(tipo: HazardType) -> str:
    """Misma idea que el mapa `TIPOS` de la vista pública, centralizada aquí
    para que el panel del operador no duplique su propia versión."""
    return _TEXTO_TIPO_PELIGRO.get(tipo, tipo.value.replace("_", " ").capitalize())


@dataclass(frozen=True)
class NivelRiesgo:
    etiqueta: str
    detalle: str


def nivel_riesgo_municipal(alertas_criticas: int, alertas_activas: int) -> NivelRiesgo:
    """Lectura rápida de tres escalones a partir de conteos ya calculados.

    No es el puntaje de riesgo por tramo del §20.3 (ese es para rutas
    individuales); es "¿hay algo crítico corriendo ahora mismo, o no?" para
    la tarjeta de resumen del tablero.
    """
    if alertas_criticas > 0:
        return NivelRiesgo("Alto", "Hay alertas críticas vigentes: priorizar respuesta")
    if alertas_activas > 0:
        return NivelRiesgo("Medio", "Alertas vigentes sin nivel crítico: mantener monitoreo")
    return NivelRiesgo("Bajo", "Sin alertas vigentes en el municipio")
