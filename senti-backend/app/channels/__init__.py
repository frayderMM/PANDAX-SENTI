"""Canales de entrega distintos de la API propia (§10).

Un canal transporta; no decide. Lo que se dice sale de `app.rules` y del
orquestador, igual para la app, la PWA y WhatsApp.
"""

from app.channels.whatsapp import (
    WhatsAppError,
    WhatsAppNoConfigurado,
    enviar_texto,
    enviar_ubicacion,
    estado_conexion,
    normalizar_numero,
)

__all__ = [
    "WhatsAppError",
    "WhatsAppNoConfigurado",
    "enviar_texto",
    "enviar_ubicacion",
    "estado_conexion",
    "normalizar_numero",
]
