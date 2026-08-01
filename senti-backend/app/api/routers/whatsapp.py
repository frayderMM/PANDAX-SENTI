"""Entrada de WhatsApp por Evolution API (§10.1).

El webhook hace tres cosas y ninguna más: comprueba quién llama, descarta lo
que no debe procesarse y encola. **No responde al ciudadano desde aquí.**

El motivo es medido: una respuesta puede tardar decenas de segundos, y
Evolution reintenta el webhook si no recibe un 2xx enseguida. Contestar dentro
del webhook produce mensajes duplicados y una cola que se realimenta sola,
justo cuando hay una emergencia y llegan todos a la vez. Se encola en el mismo
worker que ya calcula las respuestas diferidas del §29.
"""

from __future__ import annotations

import hmac
import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.core.config import settings
from app.core.queue import cliente_valkey

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["whatsapp"])

# Un id ya visto no se vuelve a procesar. Doce horas cubre de sobra los
# reintentos de Evolution sin llenar Valkey de claves eternas.
_TTL_DEDUPE_S = 12 * 3600


def _ya_procesado(message_id: str) -> bool:
    """True si este mensaje ya se encoló antes.

    Evolution reintenta cuando tarda la respuesta, y sin esto el ciudadano
    recibe la misma orientación tres veces. Se usa `SET NX`, que es atómico:
    dos réplicas del webhook procesando el mismo reintento no pueden colarse
    las dos.
    """
    r = cliente_valkey()
    if r is None:
        # Sin Valkey no se puede deduplicar. Se procesa igual: repetir una
        # instrucción de seguridad molesta; perderla no es aceptable.
        logger.warning("sin Valkey: no se puede deduplicar el mensaje %s", message_id)
        return False
    return not r.set(f"wa:visto:{message_id}", "1", nx=True, ex=_TTL_DEDUPE_S)


def _texto_del_mensaje(mensaje: dict[str, Any]) -> str | None:
    """Saca el texto de las formas en que Baileys lo puede mandar."""
    if not isinstance(mensaje, dict):
        return None
    directo = mensaje.get("conversation")
    if isinstance(directo, str) and directo.strip():
        return directo.strip()
    extendido = mensaje.get("extendedTextMessage")
    if isinstance(extendido, dict):
        texto = extendido.get("text")
        if isinstance(texto, str) and texto.strip():
            return texto.strip()
    # Pie de foto: el §25 permite observar una imagen, y el texto que la
    # acompaña suele ser la pregunta de verdad.
    for clave in ("imageMessage", "videoMessage", "documentMessage"):
        media = mensaje.get(clave)
        if isinstance(media, dict):
            pie = media.get("caption")
            if isinstance(pie, str) and pie.strip():
                return pie.strip()
    return None


def _ubicacion_del_mensaje(mensaje: dict[str, Any]) -> tuple[float, float] | None:
    """§: la ubicación llega como coordenadas del teléfono, nunca escrita."""
    if not isinstance(mensaje, dict):
        return None
    for clave in ("locationMessage", "liveLocationMessage"):
        loc = mensaje.get(clave)
        if isinstance(loc, dict):
            lat, lon = loc.get("degreesLatitude"), loc.get("degreesLongitude")
            if isinstance(lat, int | float) and isinstance(lon, int | float):
                return float(lat), float(lon)
    return None


@router.post("/whatsapp", status_code=status.HTTP_200_OK)
async def recibir(
    request: Request,
    x_senti_token: str | None = Header(default=None, alias="X-Senti-Token"),
) -> dict:
    """Recibe un evento de Evolution y lo encola.

    Devuelve 200 siempre que el evento se haya entendido, incluso cuando se
    descarta: un 4xx haría que Evolution reintente algo que ya decidimos no
    procesar.
    """
    if not settings.whatsapp_enabled:
        # Un canal de emergencia a medio configurar que traga mensajes en
        # silencio es peor que uno que declara que no está disponible.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El canal de WhatsApp no está habilitado en este despliegue.",
        )

    # Evolution no firma sus peticiones. Sin un secreto compartido, cualquiera
    # que descubra la URL puede inyectar mensajes y hacer que SENTI le escriba
    # a quien quiera, con el número de SENTI. `compare_digest` para no filtrar
    # el secreto por el tiempo de comparación.
    esperado = settings.whatsapp_webhook_token
    if not esperado or not hmac.compare_digest(x_senti_token or "", esperado):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido.")

    payload = await request.json()
    datos = payload.get("data") or {}
    clave = datos.get("key") or {}

    # §15 de la guía de Evolution: el propio envío de SENTI vuelve como evento.
    # Sin este filtro el bot se contesta a sí mismo en bucle.
    if clave.get("fromMe") is True:
        return {"estado": "ignorado", "motivo": "mensaje propio"}

    message_id = clave.get("id")
    remitente = clave.get("remoteJid") or ""
    if not message_id or not remitente:
        return {"estado": "ignorado", "motivo": "evento sin identificador"}

    # Los grupos quedan fuera: el §13.2 no permite tratar datos de terceros que
    # no han consentido, y en un grupo cada mensaje arrastra a todos.
    if remitente.endswith("@g.us"):
        return {"estado": "ignorado", "motivo": "mensaje de grupo"}

    if _ya_procesado(message_id):
        return {"estado": "ignorado", "motivo": "duplicado"}

    mensaje = datos.get("message") or {}
    texto = _texto_del_mensaje(mensaje)
    ubicacion = _ubicacion_del_mensaje(mensaje)
    if texto is None and ubicacion is None:
        return {"estado": "ignorado", "motivo": "sin texto ni ubicación"}

    from app.tasks.celery_app import atender_whatsapp

    atender_whatsapp.apply_async(
        kwargs={
            "remitente": remitente,
            "texto": texto or "",
            "lat": ubicacion[0] if ubicacion else None,
            "lon": ubicacion[1] if ubicacion else None,
        },
        # §29: la prioridad la fija el nivel de urgencia, y ese lo decide el
        # orquestador. Aquí todavía no se conoce, así que entra por la cola
        # general y el worker lo reencola si hace falta.
        queue="amarillo",
    )
    return {"estado": "encolado"}
