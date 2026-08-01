"""Conversaciones, incidentes y planes familiares (§16, §17, §18)."""

from __future__ import annotations

import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain import Channel, HazardType, OperationLevel, UrgencyLevel
from app.models.base import SRID, Base, Timestamped, UUIDPrimaryKey
from app.models.enums_sa import (
    channel_enum,
    hazard_type_enum,
    operation_level_enum,
    urgency_enum,
)


class Conversation(UUIDPrimaryKey, Timestamped, Base):
    """§10.1: la ventana de servicio de WhatsApp dura 24 h y se reinicia con
    cada mensaje del usuario.

    `ventana_servicio_hasta` es lo que decide si una respuesta es gratuita o
    exige plantilla aprobada con costo. Fuera de la ventana SENTI no puede
    responder libremente: solo puede iniciar con plantilla utilitaria.
    """

    __tablename__ = "conversations"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    canal: Mapped[Channel] = mapped_column(channel_enum, default=Channel.PWA, nullable=False)
    # §13.5: seudonimizado, nunca el número en claro.
    phone_pseudonym: Mapped[str | None] = mapped_column(String(64), index=True)
    ventana_servicio_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    modo_ligero: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    nivel_operacion: Mapped[OperationLevel] = mapped_column(
        operation_level_enum, default=OperationLevel.N0_NORMAL, nullable=False
    )
    # §7.4: el modo ligero se activa tras dos fallos seguidos de envío de media.
    fallos_media_consecutivos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # §13.1 y §13.4: consentimiento de quien escribe por WhatsApp y no tiene
    # cuenta. No puede ir en `consents`, que cuelga de un usuario. Se guarda
    # cuándo aceptó y qué versión del aviso, porque demostrar el consentimiento
    # exige poder reproducir qué se aceptó, no solo que se aceptó.
    consentimiento_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consentimiento_version: Mapped[str | None] = mapped_column(String(32))
    # Última ubicación compartida en la conversación.
    #
    # En WhatsApp la ubicación y la pregunta son mensajes distintos: se
    # comparte el punto y a continuación se escribe "¿por dónde salgo?". Sin
    # recordarla, el segundo mensaje llega sin coordenadas y el sistema pide
    # otra vez lo que le acaban de dar.
    #
    # §13.5: la ubicación exacta vive 72 h. `ubicacion_at` es la marca que usa
    # `aplicar_retencion` para borrarla, y también el corte para no reutilizar
    # una posición vieja: dónde estaba alguien hace tres días no dice dónde
    # está durante una emergencia.
    ultima_lat: Mapped[float | None] = mapped_column(Float)
    ultima_lon: Mapped[float | None] = mapped_column(Float)
    ubicacion_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    activa: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # §13.5: texto de mensajes y conversación, 12 meses.
    expira_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )

    def ventana_abierta(self, ahora: datetime) -> bool:
        return self.ventana_servicio_hasta is not None and ahora <= self.ventana_servicio_hasta


class Message(UUIDPrimaryKey, Base):
    """Mensaje de la conversación, con la traza de cómo se produjo la respuesta.

    `herramientas_invocadas` y `fuentes_citadas` no son telemetría opcional: el
    §32.2 exige 100 % de respuestas que citen fuente y hora verificables, y eso
    solo se puede medir si queda registrado por mensaje.
    """

    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    rol: Mapped[str] = mapped_column(String(16), nullable=False)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    urgencia: Mapped[UrgencyLevel | None] = mapped_column(urgency_enum, index=True)
    # §29: True si se respondió con plantilla fija, sin pasar por el modelo.
    respuesta_plantilla_fija: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    modelo_usado: Mapped[str | None] = mapped_column(String(120))
    herramientas_invocadas: Mapped[list | None] = mapped_column(JSONB)
    fuentes_citadas: Mapped[list | None] = mapped_column(JSONB)
    # §32.2 mide latencia de primera respuesta por nivel (≤5 s en rojo).
    latencia_ms: Mapped[float | None] = mapped_column(Float)
    enviado_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Incident(UUIDPrimaryKey, Timestamped, Base):
    """Un caso concreto: alguien pide orientación en un lugar y un momento.

    §13.5: la ubicación exacta vive aquí y se borra a las 72 h. La versión
    reducida a distrito se conserva 12 meses. Son dos columnas distintas a
    propósito: el borrado de una no puede depender de recortar la otra.
    """

    __tablename__ = "incidents"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL")
    )
    alert_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("alerts.id", ondelete="SET NULL")
    )

    tipo: Mapped[HazardType | None] = mapped_column(hazard_type_enum)
    urgencia: Mapped[UrgencyLevel] = mapped_column(
        urgency_enum, default=UrgencyLevel.VERDE, nullable=False, index=True
    )
    descripcion: Mapped[str | None] = mapped_column(Text)

    ubicacion_exacta: Mapped[object | None] = mapped_column(
        Geometry(geometry_type="POINT", srid=SRID, spatial_index=True)
    )
    ubicacion_exacta_expira_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    distrito: Mapped[str | None] = mapped_column(String(120), index=True)
    distrito_expira_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )

    resuelto: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resuelto_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FamilyPlan(UUIDPrimaryKey, Timestamped, Base):
    """§17. Las acciones críticas provienen de protocolos configurados por el
    administrador; Gemma personaliza el orden, el ritmo y la explicación,
    nunca el contenido de una acción crítica.
    """

    __tablename__ = "family_plans"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    alert_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("alerts.id", ondelete="SET NULL")
    )
    titulo: Mapped[str] = mapped_column(String(240), nullable=False)
    horizonte_horas: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    # Snapshot del perfil con el que se generó: el plan debe poder explicarse
    # aunque el perfil cambie después.
    perfil_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    protocolo_version: Mapped[str | None] = mapped_column(String(32))
    # §26: disponible sin conexión.
    descargable_offline: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    generado_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    tasks: Mapped[list[PlanTask]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="PlanTask.prioridad"
    )


class PlanTask(UUIDPrimaryKey, Base):
    """Tarea del plan familiar (§17).

    `critica=True` marca las que vienen de protocolo y cuyo texto el modelo no
    puede reescribir. `origen_protocolo` guarda de dónde salió, para poder
    auditarlo.
    """

    __tablename__ = "plan_tasks"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("family_plans.id", ondelete="CASCADE"), index=True
    )
    prioridad: Mapped[int] = mapped_column(Integer, nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    critica: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    origen_protocolo: Mapped[str | None] = mapped_column(String(160))
    motivo_personalizacion: Mapped[str | None] = mapped_column(String(240))
    completada: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    plan: Mapped[FamilyPlan] = relationship(back_populates="tasks")
