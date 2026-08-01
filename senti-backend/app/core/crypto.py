"""Cifrado en reposo y seudonimización (§13.5, §28).

Dos primitivas, con propósitos distintos y no intercambiables:

- `encrypt_field` / `decrypt_field`: reversible, para campos sensibles del
  perfil del hogar y el teléfono del contacto de confianza. Se necesita
  recuperar el valor, así que se cifra.
- `pseudonymize_phone`: irreversible, para el número del titular. Se necesita
  reconocer al mismo usuario entre mensajes, no leer su número, así que se
  hashea con sal. El §13.5 lo exige seudonimizado, no cifrado.
"""

from __future__ import annotations

import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class FieldCipherUnavailable(RuntimeError):
    """No hay clave de cifrado configurada y se intentó cifrar un dato sensible."""


def _fernet() -> Fernet:
    key = settings.field_encryption_key
    if not key:
        raise FieldCipherUnavailable(
            "SENTI_FIELD_ENCRYPTION_KEY no está configurada. El §13.2 exige cifrado "
            "en reposo de los campos sensibles del perfil del hogar; sin clave el "
            "sistema no los almacena en vez de almacenarlos en claro."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_field(value: str | None) -> bytes | None:
    if value is None or value == "":
        return None
    return _fernet().encrypt(value.encode("utf-8"))


def decrypt_field(token: bytes | None) -> str | None:
    if not token:
        return None
    try:
        return _fernet().decrypt(token).decode("utf-8")
    except InvalidToken:
        # Credencial rotada (§28) o dato corrupto. No se adivina: se declara.
        return None


def pseudonymize_phone(phone: str) -> str:
    """Identificador estable del titular sin conservar el número (§13.5).

    HMAC-SHA256 con sal de servidor: dos ejecuciones con el mismo número dan
    el mismo identificador, pero el número no se puede recuperar del hash ni
    enumerar por fuerza bruta sin conocer la sal.

    El número se canoniza antes con `rules.phones.canonizar_telefono` para que
    la app y WhatsApp produzcan el mismo seudónimo para la misma persona.
    """
    from app.rules.phones import canonizar_telefono

    return hmac.new(
        settings.phone_hash_salt.encode("utf-8"),
        canonizar_telefono(phone).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def content_hash(payload: bytes) -> str:
    """Hash del contenido oficial ingerido (§12).

    Toda respuesta que cite una fuente oficial cita también este hash y la URL
    de origen: es la medida contra la suplantación descrita en el §12.
    """
    return hashlib.sha256(payload).hexdigest()
