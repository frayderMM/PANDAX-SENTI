"""Usuarios, roles, consentimiento y perfil del hogar (§6, §13, §14)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import Role
from app.domain import ConsentPurpose
from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums_sa import consent_purpose_enum, role_enum


class User(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "users"

    email: Mapped[str | None] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(128))
    # §13.5: el número del titular se guarda seudonimizado con hash, nunca en
    # claro, y nunca se muestra a otros usuarios (§28).
    phone_pseudonym: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(120))
    role: Mapped[Role] = mapped_column(role_enum, default=Role.CIUDADANO, nullable=False)
    municipality: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # §28: bloqueo por intentos fallidos.
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    consents: Mapped[list[Consent]] = relationship(back_populates="user")
    household: Mapped[HouseholdProfile | None] = relationship(
        back_populates="user", uselist=False
    )


class Consent(UUIDPrimaryKey, Timestamped, Base):
    """Registro de consentimiento previo, informado, expreso e inequívoco (§13.1).

    Se guarda el texto exacto mostrado y su versión: demostrar el
    consentimiento requiere poder reproducir qué se aceptó, no solo que se
    aceptó.
    """

    __tablename__ = "consents"
    __table_args__ = (UniqueConstraint("user_id", "purpose", name="uq_consent_user_purpose"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[ConsentPurpose] = mapped_column(consent_purpose_enum)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notice_version: Mapped[str] = mapped_column(String(32), nullable=False)
    notice_text: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(String(16), default="pwa")

    user: Mapped[User] = relationship(back_populates="consents")


class HouseholdProfile(UUIDPrimaryKey, Timestamped, Base):
    """Perfil del hogar (§14). Punto de mayor exposición legal del sistema (§13.2).

    Lo que NO existe en esta tabla es tan importante como lo que existe: no hay
    nombres, ni diagnósticos, ni recetas, ni identificación de terceros. Solo
    cantidad y condición, tal como exige el §13.2.

    `medicamentos_habituales` es booleano a propósito: saber que hay que
    prepararlos basta para elevar la prioridad de esa tarea en el plan (§17);
    saber cuáles son no aporta nada al plan y sí crea un dato de salud.
    """

    __tablename__ = "household_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )

    # §13.2: ubicación a nivel de zona aproximada por defecto. La ubicación
    # exacta vive en `incidents`, caduca con el incidente y se borra a las 72 h.
    distrito: Mapped[str | None] = mapped_column(String(120), index=True)
    zona_aproximada: Mapped[str | None] = mapped_column(String(120))

    integrantes: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    ninos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    adultos_mayores: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mascotas: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Datos sensibles de salud (§13.2). Cantidad y condición, nunca detalle.
    movilidad_reducida: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    discapacidad: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    medicamentos_habituales: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    vehiculo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    medio_transporte: Mapped[str | None] = mapped_column(String(32))

    punto_reunion_configurado: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    punto_reunion_descripcion: Mapped[str | None] = mapped_column(String(240))

    # §13.2: el contacto de confianza guarda SOLO el teléfono, cifrado, y nunca
    # se usa para enviarle nada sin acción del titular. Sin nombre asociado:
    # es dato personal de un tercero que no ha consentido nada.
    contacto_confianza_telefono_cifrado: Mapped[bytes | None] = mapped_column(LargeBinary)

    mochila_lista: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped[User] = relationship(back_populates="household")

    def as_routing_profile(self) -> dict:
        """Proyección mínima que necesita el motor de rutas (§14, §20.3).

        Se pasa solo lo que cambia el cálculo. El motor de rutas no tiene por
        qué conocer el resto del perfil.
        """
        return {
            "movilidad_reducida": self.movilidad_reducida,
            "adultos_mayores": self.adultos_mayores,
            "ninos": self.ninos,
            "vehiculo": self.vehiculo,
            "mascotas": self.mascotas,
        }
