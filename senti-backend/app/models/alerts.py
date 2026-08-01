"""Alertas oficiales y comunicados municipales (§15, §22)."""

from __future__ import annotations

import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain import ConfidenceLevel, HazardType
from app.models.base import SRID, Base, Timestamped, UUIDPrimaryKey
from app.models.enums_sa import confidence_enum, hazard_type_enum


class Alert(UUIDPrimaryKey, Timestamped, Base):
    """§15. Lo que Gemma NO puede tocar en esta tabla:

    nivel_oficial, vigencia_inicio, vigencia_fin, entidad_emisora y la
    geometría de `zones`. El modelo extrae y propone; el operador o el conector
    oficial son los únicos que escriben esos campos (§15, §25).
    """

    __tablename__ = "alerts"

    source_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("official_sources.id", ondelete="SET NULL"), index=True
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL")
    )

    tipo_evento: Mapped[HazardType] = mapped_column(hazard_type_enum, index=True)
    titulo: Mapped[str] = mapped_column(String(400), nullable=False)
    nivel_oficial: Mapped[str | None] = mapped_column(String(64))
    entidad_emisora: Mapped[str] = mapped_column(String(160), nullable=False)
    confianza: Mapped[ConfidenceLevel] = mapped_column(
        confidence_enum, default=ConfidenceLevel.OFICIAL, nullable=False
    )

    # §12: hash y URL de origen del documento oficial. La respuesta cita ambos.
    url_origen: Mapped[str | None] = mapped_column(String(600))
    sha256_origen: Mapped[str | None] = mapped_column(String(64))

    vigencia_inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    vigencia_fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    vigente: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Recomendaciones tal como las publica la entidad. No se reescriben: el §17
    # deja que Gemma personalice orden, ritmo y explicación, nunca el contenido
    # de una acción crítica.
    recomendaciones_oficiales: Mapped[list | None] = mapped_column(JSONB)

    # Salida del modelo sobre este documento (§15). Se guarda aparte del dato
    # oficial, nunca mezclada con él.
    resumen_modelo: Mapped[str | None] = mapped_column(Text)
    terminos_explicados: Mapped[dict | None] = mapped_column(JSONB)
    datos_faltantes: Mapped[list | None] = mapped_column(JSONB)

    actualizado_en_origen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    zones: Mapped[list[AlertZone]] = relationship(
        back_populates="alert", cascade="all, delete-orphan"
    )


class AlertZone(UUIDPrimaryKey, Base):
    """Geometría afectada por una alerta (§15).

    La pregunta "¿esta alerta afecta mi zona?" se responde cruzando esta
    geometría con la zona del perfil en PostGIS, no con el criterio del modelo
    (§15). Por eso la geometría es una columna real y no texto.
    """

    __tablename__ = "alert_zones"

    alert_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("alerts.id", ondelete="CASCADE"), index=True
    )
    nombre: Mapped[str | None] = mapped_column(String(240))
    distrito: Mapped[str | None] = mapped_column(String(120), index=True)
    provincia: Mapped[str | None] = mapped_column(String(120))
    departamento: Mapped[str | None] = mapped_column(String(120))
    geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=SRID, spatial_index=True), nullable=False
    )

    alert: Mapped[Alert] = relationship(back_populates="zones")


class MunicipalNotice(UUIDPrimaryKey, Timestamped, Base):
    """Comunicado municipal (§22).

    Se publica con entidad, responsable, fecha y vigencia, y entra al RAG con
    la precedencia del §19 (COMUNICADO_MUNICIPAL, por debajo de lo oficial y
    por encima de lo comunitario).
    """

    __tablename__ = "municipal_notices"

    municipalidad: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    responsable_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    titulo: Mapped[str] = mapped_column(String(400), nullable=False)
    cuerpo: Mapped[str] = mapped_column(Text, nullable=False)
    vigencia_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    vigencia_fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    publicado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    geom: Mapped[object | None] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=SRID, spatial_index=True)
    )


class AlertSubscriber(UUIDPrimaryKey, Timestamped, Base):
    """Destinatario de alertas por WhatsApp, por distrito (§13.4).

    Distinto a propósito de `User.phone_pseudonym`: ese es un hash de un solo
    sentido, pensado para que el sistema nunca pueda escribirle a nadie por
    su cuenta. Este modelo existe exactamente para lo contrario —el sistema
    SÍ necesita el número real para poder avisar por WhatsApp— así que solo
    se crea cuando la persona da el consentimiento explícito
    `ConsentPurpose.ALERTAS_WHATSAPP` en el registro, nunca por inferencia.

    `activo=False` es la forma de revocar sin borrar el historial de a quién
    se le mandó qué (si algún día se registra el envío); revocar el
    consentimiento en `/auth/consentimiento` pone esto en `False`.
    """

    __tablename__ = "alert_subscribers"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    nombre: Mapped[str | None] = mapped_column(String(120))
    telefono: Mapped[str] = mapped_column(String(32), nullable=False)
    distrito: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
