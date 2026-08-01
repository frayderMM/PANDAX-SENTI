"""Envío por WhatsApp a través de Evolution API (§10.1).

Este módulo es **transporte y nada más**. No decide qué se dice ni cuándo: eso
ya lo resolvió `app.rules` y lo redactó el orquestador. Aquí solo se entrega.

Dos cosas que el §7.3 impone sobre este canal y que se cumplen antes de llegar
aquí, en `rules/light_mode.py`: el texto viaja completo —fuente y hora dentro
del mensaje, porque en WhatsApp no hay interfaz donde desplegarlas— y no
depende de ningún enlace.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.core.crypto import canonizar_telefono

logger = logging.getLogger(__name__)

# Perú: 51 + 9 dígitos. Se admite cualquier país, pero se rechaza lo que no
# pueda ser un número: mandar basura a Evolution devuelve un 400 que nadie mira.
_LONGITUD_MINIMA = 8
_LONGITUD_MAXIMA = 15


class WhatsAppNoConfigurado(RuntimeError):
    """Falta la URL, la instancia o la clave. No se intenta enviar."""


class WhatsAppError(RuntimeError):
    """Evolution rechazó el envío."""


def normalizar_numero(numero: str) -> str:
    """Deja el destinatario en la forma que Evolution sabe enrutar.

    **Un JID se devuelve intacto.** WhatsApp ya no siempre identifica a quien
    escribe por su teléfono: manda un LID (`140368842588179@lid`), que no es un
    número y no se puede convertir en uno. Recortarle el sufijo producía quince
    dígitos que Evolution rechazaba con `exists: false`, así que el bot pensaba
    la respuesta, la guardaba y **no la entregaba**. Comprobado contra la
    instalación: el LID entero se acepta y el teléfono deducido no.

    Solo se limpia lo que llega como número suelto, que es lo que escribe un
    humano al configurar algo: `+51 987-654-321` → `51987654321`.

    La canonización (dígitos + `51` delante de un celular peruano de 9
    dígitos) es la misma que usa `core.crypto.canonizar_telefono` para el
    seudónimo de identidad: es el mismo problema —"925650163" y
    "51925650163@s.whatsapp.net" tienen que resolver a la misma persona y al
    mismo destinatario— resuelto una sola vez, no dos veces por separado. Sin
    esto, `AlertSubscriber.telefono` ("925650163", tal como se registra)
    llega a Evolution como 9 dígitos que no resuelven a ningún JID: el envío
    no lanza error, Evolution solo no encuentra al destinatario.
    """
    if "@" in numero:
        jid = numero.strip()
        if not jid.split("@")[0]:
            raise ValueError(f"identificador de WhatsApp vacío: {numero!r}")
        return jid

    limpio = canonizar_telefono(numero)
    if not (_LONGITUD_MINIMA <= len(limpio) <= _LONGITUD_MAXIMA):
        raise ValueError(f"número de WhatsApp no utilizable: {numero!r}")
    return limpio


def _configurado() -> tuple[str, str, str]:
    url = settings.evolution_api_url.rstrip("/")
    instancia = settings.evolution_instance
    clave = settings.evolution_api_key
    if not (settings.whatsapp_enabled and url and instancia and clave):
        raise WhatsAppNoConfigurado(
            "WhatsApp no está configurado: faltan SENTI_WHATSAPP_ENABLED, "
            "SENTI_EVOLUTION_API_URL, SENTI_EVOLUTION_INSTANCE o "
            "SENTI_EVOLUTION_API_KEY."
        )
    return url, instancia, clave


def _peticion(ruta: str, cuerpo: dict, *, timeout: float = 30.0) -> dict:
    url, instancia, clave = _configurado()
    destino = f"{url}/{ruta}/{instancia}"
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.post(destino, json=cuerpo, headers={"apikey": clave})
    except httpx.HTTPError as exc:
        raise WhatsAppError(f"no se pudo hablar con Evolution: {exc}") from exc

    if r.status_code >= 400:
        # El cuerpo se registra recortado: lleva el número del destinatario y
        # el §13.2 no lo quiere entero en los logs.
        raise WhatsAppError(f"Evolution devolvió {r.status_code}: {r.text[:200]}")
    return r.json() if r.content else {}


def enviar_texto(numero: str, texto: str) -> dict:
    """Envía un mensaje de texto.

    `linkPreview` va en false a propósito: el §7.3 dice que ninguna instrucción
    depende de abrir un enlace, y una previsualización invita justo a eso. El
    texto tiene que bastar solo.
    """
    return _peticion(
        "message/sendText",
        {"number": normalizar_numero(numero), "text": texto, "linkPreview": False},
    )


def enviar_ubicacion(numero: str, lat: float, lon: float, nombre: str) -> dict:
    """Envía un punto del mapa.

    Se usa para señalar un recurso ya validado, nunca para dar la instrucción:
    los pasos van siempre en el texto (§7.3). Si esto falla, el mensaje sigue
    siendo accionable.
    """
    return _peticion(
        "message/sendLocation",
        {
            "number": normalizar_numero(numero),
            "latitude": lat,
            "longitude": lon,
            "name": nombre,
            "address": nombre,
        },
    )


def estado_conexion() -> dict:
    """Estado de la instancia. `state: "open"` es el único que puede enviar."""
    url, instancia, clave = _configurado()
    try:
        with httpx.Client(timeout=10.0) as c:
            r = c.get(
                f"{url}/instance/connectionState/{instancia}",
                headers={"apikey": clave},
            )
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as exc:
        raise WhatsAppError(f"no se pudo consultar el estado: {exc}") from exc
