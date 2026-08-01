"""Autenticación y permisos (§6, §28).

Los permisos se validan aquí, en el backend, nunca solo en el frontend (§28).
La matriz del §6 se codifica en `ROLE_PERMISSIONS` y es la única fuente de
verdad sobre quién puede hacer qué.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import settings

ALGORITHM = "HS256"


class Role(str, enum.Enum):
    CIUDADANO = "ciudadano"
    VALIDADOR = "validador"
    OPERADOR_MUNICIPAL = "operador_municipal"
    ADMINISTRADOR = "administrador"


class Permission(str, enum.Enum):
    CONSULTAR_ALERTAS = "consultar_alertas"
    CONFIGURAR_HOGAR = "configurar_hogar"
    USAR_CHAT = "usar_chat"
    GENERAR_PLAN = "generar_plan"
    CONSULTAR_RUTAS = "consultar_rutas"
    CREAR_REPORTE = "crear_reporte"
    VALIDAR_REPORTE = "validar_reporte"
    CONFIRMAR_CIERRE_VIA = "confirmar_cierre_via"
    REGISTRAR_RECURSO = "registrar_recurso"
    PUBLICAR_COMUNICADO = "publicar_comunicado"
    GESTIONAR_USUARIOS_Y_FUENTES = "gestionar_usuarios_y_fuentes"
    CONSULTAR_AUDITORIA = "consultar_auditoria"
    CONSULTAR_AUDITORIA_PROPIA = "consultar_auditoria_propia"


# Matriz del §6, literal.
#
# Nota sobre las dos filas que el §6 marca como "Limitado": el validador y el
# operador municipal ven auditoría de sus propias acciones y de las entidades
# que les competen, no la auditoría completa. Se modela como un permiso
# distinto, no como una versión debilitada del mismo.
ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.CIUDADANO: frozenset(
        {
            Permission.CONSULTAR_ALERTAS,
            Permission.CONFIGURAR_HOGAR,
            Permission.USAR_CHAT,
            Permission.GENERAR_PLAN,
            Permission.CONSULTAR_RUTAS,
            Permission.CREAR_REPORTE,
        }
    ),
    Role.VALIDADOR: frozenset(
        {
            Permission.CONSULTAR_ALERTAS,
            Permission.USAR_CHAT,
            Permission.CONSULTAR_RUTAS,
            Permission.CREAR_REPORTE,
            Permission.VALIDAR_REPORTE,
            Permission.CONSULTAR_AUDITORIA_PROPIA,
        }
    ),
    Role.OPERADOR_MUNICIPAL: frozenset(
        {
            Permission.CONSULTAR_ALERTAS,
            Permission.USAR_CHAT,
            Permission.CONSULTAR_RUTAS,
            Permission.CREAR_REPORTE,
            Permission.VALIDAR_REPORTE,
            Permission.CONFIRMAR_CIERRE_VIA,
            Permission.REGISTRAR_RECURSO,
            Permission.PUBLICAR_COMUNICADO,
            Permission.CONSULTAR_AUDITORIA_PROPIA,
        }
    ),
    Role.ADMINISTRADOR: frozenset(
        {
            Permission.CONSULTAR_ALERTAS,
            Permission.USAR_CHAT,
            Permission.CONSULTAR_RUTAS,
            Permission.GESTIONAR_USUARIOS_Y_FUENTES,
            Permission.CONSULTAR_AUDITORIA,
        }
    ),
}


def has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str, role: Role) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "role": role.value,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
