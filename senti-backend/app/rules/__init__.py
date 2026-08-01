"""Reglas duras del sistema.

Todo lo que hay aquí es determinista, sin red y sin base de datos: recibe
hechos y devuelve decisiones. Es lo que hace posible el §29 ("las respuestas de
nivel rojo deben ser correctas con el modelo apagado") y lo que se mide contra
el §32.2.

Ningún módulo de este paquete importa `app.llm` ni `app.models`. Si alguna vez
hace falta, la regla está mal planteada.
"""

from app.rules import (
    fixed_responses,
    light_mode,
    phones,
    response,
    retention,
    scoring,
    trust,
    urgency,
)

__all__ = [
    "fixed_responses",
    "light_mode",
    "phones",
    "response",
    "retention",
    "scoring",
    "trust",
    "urgency",
]
