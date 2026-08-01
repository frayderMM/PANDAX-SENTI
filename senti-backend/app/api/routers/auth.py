"""Registro, acceso y consentimiento granular (§6, §13.4, RF-01)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import auditar, db, usuario_actual
from app.core.crypto import pseudonymize_phone
from app.core.security import Role, create_access_token, hash_password, verify_password
from app.domain import ConsentPurpose
from app.models import AlertSubscriber, Consent, User
from app.rules.fixed_responses import CONSENTIMIENTO_VERSION, CONSENTIMIENTO_WHATSAPP

router = APIRouter(prefix="/auth", tags=["identidad"])

# §28: bloqueo por intentos fallidos.
MAX_INTENTOS = 5
BLOQUEO = timedelta(minutes=15)


class RegistroEntrada(BaseModel):
    email: EmailStr
    # Sin longitud mínima, por decisión de producto: en una emergencia se
    # registra gente con prisa y desde teclados incómodos. El máximo se queda
    # porque bcrypt trunca a 72 bytes y aceptar entradas enormes solo regala
    # trabajo de hash a quien quiera saturar el registro.
    password: str = Field(min_length=1, max_length=128)
    display_name: str | None = Field(default=None, max_length=120)
    telefono: str | None = Field(default=None, max_length=32)
    # §6: el rol lo asigna el administrador. El registro público solo crea
    # ciudadanos; permitir elegirlo aquí sería una escalada de privilegios.
    municipality: str | None = None
    # Consentimiento explícito y aparte del checkbox de mensajería: aceptar
    # que SENTI guarde el teléfono en claro para escribir por iniciativa
    # propia es una finalidad distinta a que conteste cuando el ciudadano
    # escribe primero (§13.4).
    recibir_alertas_whatsapp: bool = False


class LoginEntrada(BaseModel):
    email: EmailStr
    password: str


class TokenSalida(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    expires_in: int


class ConsentimientoEntrada(BaseModel):
    purpose: ConsentPurpose
    granted: bool


@router.post("/registro", response_model=TokenSalida, status_code=status.HTTP_201_CREATED)
def registro(datos: RegistroEntrada, request: Request, session: Session = Depends(db)):
    if session.scalar(select(User).where(User.email == datos.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese correo ya está registrado")

    if datos.recibir_alertas_whatsapp and not (datos.telefono and datos.municipality):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Para recibir alertas por WhatsApp hacen falta teléfono y distrito (§13.4)",
        )

    user = User(
        email=datos.email,
        password_hash=hash_password(datos.password),
        display_name=datos.display_name,
        # §13.5: el número se guarda seudonimizado, nunca en claro. Esto no
        # cambia aunque haya alertas de WhatsApp: ese consentimiento vive
        # aparte, en `AlertSubscriber`, con el teléfono real.
        phone_pseudonym=pseudonymize_phone(datos.telefono) if datos.telefono else None,
        role=Role.CIUDADANO,
        municipality=datos.municipality,
    )
    session.add(user)
    session.flush()

    auditar(session, request, actor=user, accion="auth.registro", entidad="user",
            entidad_id=str(user.id))

    if datos.recibir_alertas_whatsapp:
        ahora = datetime.now(UTC)
        session.add(
            Consent(
                user_id=user.id,
                purpose=ConsentPurpose.ALERTAS_WHATSAPP,
                granted=True,
                granted_at=ahora,
                notice_version=CONSENTIMIENTO_VERSION,
                notice_text=_DESCRIPCION_FINALIDAD[ConsentPurpose.ALERTAS_WHATSAPP],
            )
        )
        session.add(
            AlertSubscriber(
                user_id=user.id,
                nombre=datos.display_name,
                telefono=datos.telefono,
                distrito=datos.municipality,
                activo=True,
            )
        )
        auditar(session, request, actor=user, accion="alertas_whatsapp.suscribir",
                entidad="alert_subscriber", entidad_id=str(user.id),
                detalle={"distrito": datos.municipality})

    from app.core.config import settings

    return TokenSalida(
        access_token=create_access_token(str(user.id), user.role),
        role=user.role.value,
        expires_in=settings.access_token_minutes * 60,
    )


@router.post("/login", response_model=TokenSalida)
def login(datos: LoginEntrada, request: Request, session: Session = Depends(db)):
    user = session.scalar(select(User).where(User.email == datos.email))
    ahora = datetime.now(UTC)

    if user and user.locked_until and user.locked_until > ahora:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Cuenta bloqueada temporalmente por intentos fallidos (§28)",
        )

    if user is None or not verify_password(datos.password, user.password_hash or ""):
        if user is not None:
            user.failed_login_count += 1
            if user.failed_login_count >= MAX_INTENTOS:
                user.locked_until = ahora + BLOQUEO
                user.failed_login_count = 0
            auditar(session, request, actor=None, accion="auth.login_fallido",
                    entidad="user", entidad_id=str(user.id))
        # Mismo mensaje exista o no el usuario: no se confirma qué correos
        # están registrados.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas")

    user.failed_login_count = 0
    user.locked_until = None
    user.last_seen_at = ahora
    auditar(session, request, actor=user, accion="auth.login", entidad="user",
            entidad_id=str(user.id))

    from app.core.config import settings

    return TokenSalida(
        access_token=create_access_token(str(user.id), user.role),
        role=user.role.value,
        expires_in=settings.access_token_minutes * 60,
    )


@router.get("/aviso-consentimiento")
def aviso_consentimiento() -> dict:
    """§13.4. El texto exacto que se muestra, con su versión.

    Se devuelve versionado porque `consents.notice_text` guarda lo que la
    persona vio: demostrar el consentimiento exige poder reproducir qué se
    aceptó, no solo que se aceptó.
    """
    return {
        "version": CONSENTIMIENTO_VERSION,
        "texto_whatsapp": CONSENTIMIENTO_WHATSAPP,
        "finalidades": [
            {
                "purpose": p.value,
                "obligatoria": p is ConsentPurpose.MENSAJES,
                "descripcion": _DESCRIPCION_FINALIDAD[p],
            }
            for p in ConsentPurpose
        ],
        "nota": (
            "Negarse no bloquea el servicio básico: protocolos, teléfonos e "
            "información oficial general siguen disponibles (§13.4)."
        ),
    }


_DESCRIPCION_FINALIDAD = {
    ConsentPurpose.MENSAJES: "Guardar tus mensajes para poder responderte. 12 meses.",
    ConsentPurpose.UBICACION_EXACTA: "Usar tu ubicación exacta para calcular rutas. 72 horas.",
    ConsentPurpose.FOTOGRAFIA: "Usar tu foto solo para este caso. 30 días.",
    ConsentPurpose.PERFIL_HOGAR: (
        "Guardar cuántas personas viven contigo y qué condiciones tienen, sin "
        "nombres ni diagnósticos, para personalizar el plan. Mientras exista la cuenta."
    ),
    ConsentPurpose.CONTACTO_CONFIANZA: (
        "Guardar cifrado el teléfono de tu contacto. Nunca le escribimos sin que tú lo pidas."
    ),
    ConsentPurpose.ALERTAS_WHATSAPP: (
        "Guardar tu teléfono en claro, junto a tu distrito, para avisarte por "
        "WhatsApp cuando haya una alerta oficial de tu zona. A diferencia de "
        "las demás finalidades, esta permite que SENTI te escriba primero."
    ),
}


@router.post("/consentimiento")
def registrar_consentimiento(
    datos: ConsentimientoEntrada,
    request: Request,
    session: Session = Depends(db),
    user: User = Depends(usuario_actual),
) -> dict:
    """§13.4: consentimiento granular, por finalidad, revocable."""
    ahora = datetime.now(UTC)
    consent = session.scalar(
        select(Consent).where(Consent.user_id == user.id, Consent.purpose == datos.purpose)
    )
    if consent is None:
        consent = Consent(
            user_id=user.id,
            purpose=datos.purpose,
            granted=datos.granted,
            notice_version=CONSENTIMIENTO_VERSION,
            notice_text=_DESCRIPCION_FINALIDAD[datos.purpose],
        )
        session.add(consent)
    else:
        consent.granted = datos.granted
        consent.notice_version = CONSENTIMIENTO_VERSION

    consent.granted_at = ahora if datos.granted else consent.granted_at
    consent.revoked_at = None if datos.granted else ahora

    # ALERTAS_WHATSAPP aquí no solo anota el consentimiento: apaga o prende
    # el envío real (§13.4, revocable). Revocar desactiva toda suscripción
    # existente; volver a otorgar reactiva la que ya tenía teléfono y
    # distrito, sin pedirlos otra vez —este endpoint no los recibe—. Si
    # nunca hubo una (`registro` es el único que la crea, con consentimiento
    # inicial), no hay nada que reactivar.
    if datos.purpose is ConsentPurpose.ALERTAS_WHATSAPP:
        suscripciones = session.scalars(
            select(AlertSubscriber).where(AlertSubscriber.user_id == user.id)
        )
        for suscripcion in suscripciones:
            suscripcion.activo = datos.granted

    auditar(session, request, actor=user, accion="consentimiento.actualizar",
            entidad="consent", entidad_id=datos.purpose.value,
            detalle={"granted": datos.granted})

    return {"purpose": datos.purpose.value, "granted": datos.granted,
            "version": CONSENTIMIENTO_VERSION}


@router.get("/mis-datos")
def mis_datos(session: Session = Depends(db), user: User = Depends(usuario_actual)) -> dict:
    """§13.4: `MIS DATOS` devuelve qué se guardó y hasta cuándo."""
    from app.rules.retention import AvisoRetencion

    consents = list(session.scalars(select(Consent).where(Consent.user_id == user.id)))
    suscripcion_activa = session.scalar(
        select(AlertSubscriber).where(
            AlertSubscriber.user_id == user.id, AlertSubscriber.activo.is_(True)
        )
    )
    return {
        "retencion": AvisoRetencion.completo().render(),
        "consentimientos": [
            {
                "purpose": c.purpose.value,
                "granted": c.granted,
                "desde": c.granted_at.isoformat() if c.granted_at else None,
                "revocado": c.revoked_at.isoformat() if c.revoked_at else None,
            }
            for c in consents
        ],
        "telefono": (
            f"guardado en claro para avisarte por WhatsApp de alertas en "
            f"{suscripcion_activa.distrito}; revócalo con ALERTAS_WHATSAPP en /auth/consentimiento"
            if suscripcion_activa
            else "seudonimizado con hash; el número no se conserva"
        ),
    }
