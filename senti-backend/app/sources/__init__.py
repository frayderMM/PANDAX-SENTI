"""Conectores y salud de fuentes oficiales (§11)."""

from app.sources.health import HealthResult, comprobar, declarar_ausencia, hash_esquema
from app.sources.registry import CATALOGO, POR_SLUG, SourceDef, fuentes_para

__all__ = [
    "CATALOGO",
    "POR_SLUG",
    "HealthResult",
    "SourceDef",
    "comprobar",
    "declarar_ausencia",
    "fuentes_para",
    "hash_esquema",
]
