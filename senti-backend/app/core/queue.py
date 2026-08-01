"""Profundidad de la cola del modelo (§29).

    Si la cola del modelo supera el umbral:
       → rojo y negro responden con PLANTILLAS FIJAS, sin pasar por el modelo
       → amarillo y verde reciben acuse y respuesta diferida

Esa regla estaba implementada pero nunca se activaba, porque nadie medía la
cola: `profundidad_cola` llegaba siempre a 0. Este módulo la mide.

**Por qué un conjunto ordenado y no un contador.** Un `INCR`/`DECR` es más
simple, pero si un proceso muere entre el incremento y el decremento el
contador queda alto para siempre, y a partir de ahí el sistema responde con
plantillas fijas aunque no haya carga. En un sistema de emergencias, una
degradación permanente e invisible es peor que no degradar.

Aquí cada petición en vuelo es un miembro con su marca de tiempo, y contar
descarta las caducadas. Un worker que muere deja basura que se limpia sola en
`TTL_SEGUNDOS`.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import contextmanager

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

CLAVE = "senti:llm:en_vuelo"
# Más que el timeout del modelo, para que una petición lenta pero viva siga
# contando. Menos que un minuto, para que la basura de un worker caído no
# distorsione la medida mucho tiempo.
TTL_SEGUNDOS = 180.0

_cliente: redis.Redis | None = None


def _redis() -> redis.Redis:
    global _cliente
    if _cliente is None:
        _cliente = redis.Redis.from_url(settings.valkey_url, decode_responses=True)
    return _cliente


def cliente_valkey() -> redis.Redis | None:
    """Cliente listo para usar, o `None` si Valkey no responde.

    Devuelve `None` en vez de propagar para que quien lo use decida qué hacer
    sin Valkey. No todos deciden igual: la profundidad de cola falla hacia "no
    degradar", y la deduplicación de WhatsApp falla hacia "procesar igual",
    porque repetir una instrucción de seguridad molesta y perderla no.
    """
    try:
        r = _redis()
        r.ping()
        return r
    except redis.RedisError as exc:
        logger.warning("Valkey no responde: %s", exc)
        return None


def profundidad() -> int:
    """Peticiones al modelo actualmente en vuelo.

    Si Valkey no responde devuelve 0, es decir, "no degradar". Es deliberado:
    la degradación del §29 existe para proteger al sistema bajo carga, y
    activarla por un fallo del contador dejaría a todo el mundo con plantillas
    fijas sin que hubiera carga alguna.
    """
    try:
        r = _redis()
        limite = time.time() - TTL_SEGUNDOS
        r.zremrangebyscore(CLAVE, "-inf", limite)
        return int(r.zcard(CLAVE))
    except redis.RedisError as exc:
        logger.warning("No se pudo medir la cola del modelo: %s", exc)
        return 0


@contextmanager
def en_vuelo():
    """Marca una petición al modelo mientras dura.

    Si Valkey falla, la petición sigue adelante sin contarse: medir la carga no
    puede ser motivo para no atender a alguien.
    """
    marca = uuid.uuid4().hex
    r = None
    try:
        r = _redis()
        r.zadd(CLAVE, {marca: time.time()})
        r.expire(CLAVE, int(TTL_SEGUNDOS * 2))
    except redis.RedisError as exc:
        logger.warning("No se pudo registrar la petición en la cola: %s", exc)
        r = None
    try:
        yield
    finally:
        if r is not None:
            try:
                r.zrem(CLAVE, marca)
            except redis.RedisError:
                # La entrada caduca sola por TTL; no se pierde nada permanente.
                pass
