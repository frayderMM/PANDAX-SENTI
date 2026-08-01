"""Auditoría, retención y parámetros del motor de riesgo (§13.5, §23, §27)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamped, UUIDPrimaryKey


class AuditLog(UUIDPrimaryKey, Base):
    """§27: registra toda acción sensible con usuario, entidad, fecha y detalle.

    §13.5: retención de 24 meses, la más larga de todo el sistema. Es
    deliberado: la auditoría sobrevive a los datos que audita, porque su
    función es poder explicar una decisión pasada (§23) cuando el dato personal
    que la originó ya se borró.
    """

    __tablename__ = "audit_logs"

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    actor_rol: Mapped[str | None] = mapped_column(String(32))
    accion: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entidad: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entidad_id: Mapped[str | None] = mapped_column(String(64), index=True)
    detalle: Mapped[dict | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(String(64))
    ocurrido_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    expira_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class RetentionJob(UUIDPrimaryKey, Timestamped, Base):
    """Una ejecución de la política de retención del §13.5.

    Se registra qué se borró y cuánto: un borrado que no deja constancia no se
    puede demostrar ante la ANPD, y el DS 016-2024-JUS exige medidas de
    seguridad demostrables (§13.1).
    """

    __tablename__ = "retention_jobs"

    politica: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ejecutado_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    filas_afectadas: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    exito: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    detalle: Mapped[str | None] = mapped_column(Text)


class RiskParameters(UUIDPrimaryKey, Timestamped, Base):
    """Parámetros del motor de riesgo, versionados (§23).

    "Todo cambio de parámetro del motor de riesgo queda versionado y auditado:
    una ruta pasada debe poder explicarse con los parámetros vigentes en su
    momento." Por eso no se editan: se crea una versión nueva y se desactiva la
    anterior.
    """

    __tablename__ = "risk_parameters"

    version: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    # Pesos del §20.3. Deben sumar 1.0; lo verifica `app.rules.scoring`.
    pesos: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Riesgo por tramo del §20.3.
    riesgos: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Vigencias por tipo de peligro (§20.3, decaimiento temporal).
    vigencias_horas: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # §20.4: umbral de cobertura cartográfica, registrado por distrito.
    umbrales_cobertura: Mapped[dict | None] = mapped_column(JSONB)
    creado_por_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    nota: Mapped[str | None] = mapped_column(Text)


class Protocol(UUIDPrimaryKey, Timestamped, Base):
    """Protocolo configurado por el administrador (§17, §23).

    Es la fuente de las acciones críticas del plan familiar. El texto de una
    acción crítica sale de aquí y el modelo no lo reescribe.
    """

    __tablename__ = "protocols"

    codigo: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    titulo: Mapped[str] = mapped_column(String(240), nullable=False)
    hazard_type: Mapped[str | None] = mapped_column(String(40), index=True)
    entidad: Mapped[str | None] = mapped_column(String(160))
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Lista de acciones: [{"texto": ..., "prioridad": n, "critica": bool,
    #                      "condicion_hogar": {...}}]
    acciones: Mapped[list] = mapped_column(JSONB, nullable=False)


class EmergencyPhone(UUIDPrimaryKey, Timestamped, Base):
    """§24.3: la tabla de teléfonos es configurable por región, no texto fijo
    en el código.

    El 911 opera en fase de pruebas como número único en Lima Metropolitana y
    Callao, así que la cobertura regional no es un detalle: es la razón de que
    esta tabla exista.
    """

    __tablename__ = "emergency_phones"

    region: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    situacion: Mapped[str] = mapped_column(String(240), nullable=False)
    numero: Mapped[str] = mapped_column(String(40), nullable=False)
    entidad: Mapped[str | None] = mapped_column(String(160))
    orden: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
