"""Dependencias de FastAPI: autenticación, permisos y contexto (§6, §28)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.security import Permission, decode_access_token, has_permission
from app.models import AuditLog, User
from app.orchestrator import ToolContext

bearer = HTTPBearer(auto_error=False)


def db() -> Iterator[Session]:
    yield from get_session()


def usuario_opcional(
    cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: Session = Depends(db),
) -> User | None:
    """§13.4: existe un modo invitado que no exige cuenta y da información general."""
    if cred is None:
        return None
    try:
        payload = decode_access_token(cred.credentials)
    except jwt.PyJWTError:
        return None
    return session.scalar(select(User).where(User.id == payload.get("sub")))


def usuario_actual(
    cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: Session = Depends(db),
) -> User:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta el token de acceso")
    try:
        payload = decode_access_token(cred.credentials)
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expirado") from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido") from exc

    user = session.scalar(select(User).where(User.id == payload.get("sub")))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario no válido")
    return user


def exige(permiso: Permission):
    """§28: los permisos se validan en el backend, nunca solo en el frontend."""

    def dependencia(user: User = Depends(usuario_actual)) -> User:
        if not has_permission(user.role, permiso):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"El rol '{user.role.value}' no tiene el permiso '{permiso.value}' (§6)",
            )
        return user

    return dependencia


def contexto_herramientas(
    user: User | None = Depends(usuario_opcional),
    session: Session = Depends(db),
) -> ToolContext:
    return ToolContext(session=session, user=user, ahora=datetime.now(UTC))


def auditar(
    session: Session,
    request: Request,
    *,
    actor: User | None,
    accion: str,
    entidad: str,
    entidad_id: str | None = None,
    detalle: dict | None = None,
) -> None:
    """§18/§27: toda acción sensible queda registrada.

    §13.5: la auditoría vive 24 meses, más que los datos que audita.
    """
    from app.rules.retention import RetentionPolicy, expira_en

    ahora = datetime.now(UTC)
    session.add(
        AuditLog(
            actor_id=actor.id if actor else None,
            actor_rol=actor.role.value if actor else None,
            accion=accion,
            entidad=entidad,
            entidad_id=entidad_id,
            detalle=detalle,
            ip=request.client.host if request.client else None,
            ocurrido_at=ahora,
            expira_at=expira_en(RetentionPolicy.AUDITORIA, ahora),
        )
    )
