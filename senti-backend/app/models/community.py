"""Reportes ciudadanos, validación y recursos (§21, §22)."""

from __future__ import annotations

import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain import HazardType, ReportState, TrustLevel
from app.models.base import SRID, Base, Timestamped, UUIDPrimaryKey
from app.models.enums_sa import hazard_type_enum, report_state_enum, trust_level_enum


class CitizenReport(UUIDPrimaryKey, Timestamped, Base):
    """§21. Un reporte NUNCA cierra una vía por sí solo.

    `trust_level` lo recalcula `app.rules.trust`, no el ciudadano ni el modelo.
    La escalera del §21.2 es: pendiente → probable (heurística de coincidencia)
    → validado (persona con rol) → confirmado (municipio o Estado).
    """

    __tablename__ = "citizen_reports"

    reporter_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    tipo: Mapped[HazardType] = mapped_column(hazard_type_enum, index=True)
    estado: Mapped[ReportState] = mapped_column(
        report_state_enum, default=ReportState.BORRADOR, nullable=False, index=True
    )
    trust_level: Mapped[TrustLevel] = mapped_column(
        trust_level_enum, default=TrustLevel.PENDIENTE, nullable=False, index=True
    )

    descripcion: Mapped[str | None] = mapped_column(Text)
    # §21.1: Gemma propone categoría y descripción; el ciudadano revisa y
    # publica. Se guarda lo que propuso el modelo aparte de lo que confirmó la
    # persona, para poder medir la calidad de la propuesta.
    categoria_propuesta_modelo: Mapped[str | None] = mapped_column(String(64))
    descripcion_propuesta_modelo: Mapped[str | None] = mapped_column(Text)
    corregido_por_ciudadano: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=SRID, spatial_index=True), nullable=False
    )
    direccion_aproximada: Mapped[str | None] = mapped_column(String(300))
    distrito: Mapped[str | None] = mapped_column(String(120), index=True)

    # §13.5: la fotografía se borra a los 30 días o al resolverse el incidente,
    # lo que ocurra antes. El EXIF se elimina al ingreso (§13.5, §28).
    foto_url: Mapped[str | None] = mapped_column(String(600))
    foto_expira_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    exif_eliminado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Observaciones del modelo sobre la imagen (§25): observaciones, nunca
    # conclusiones. "Se observa material sobre parte de la vía", no "la
    # carretera está libre por el lado izquierdo".
    observaciones_imagen: Mapped[list | None] = mapped_column(JSONB)

    reportado_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    # Vencimiento por tipo de peligro (§20.3). Pasado esto el reporte no
    # penaliza ni tranquiliza.
    vence_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    resuelto_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    duplicado_de_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("citizen_reports.id", ondelete="SET NULL")
    )

    # Identificador seudónimo para impedir que el mismo ciudadano incremente
    # el contador al reenviar el mismo aviso. Nunca se expone por API.
    reporter_key_hash: Mapped[str | None] = mapped_column(String(128), index=True)

    validations: Mapped[list[ReportValidation]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )


class EmergencyEvent(UUIDPrimaryKey, Timestamped, Base):
    """Evento agregado; los reportes son evidencias, no marcadores separados."""

    __tablename__ = "emergency_events"

    tipo: Mapped[HazardType] = mapped_column(hazard_type_enum, index=True)
    titulo: Mapped[str] = mapped_column(String(400), nullable=False)
    resumen: Mapped[str | None] = mapped_column(Text)
    distrito: Mapped[str | None] = mapped_column(String(120), index=True)
    geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=SRID, spatial_index=True), nullable=False
    )
    confianza: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    estado_validacion: Mapped[str] = mapped_column(String(32), default="SIN_CONFIRMAR")
    first_reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    reports: Mapped[list["EventCitizenReport"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    sources: Mapped[list["EventSource"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class EventCitizenReport(UUIDPrimaryKey, Base):
    __tablename__ = "event_citizen_reports"
    __table_args__ = (UniqueConstraint("event_id", "citizen_report_id", name="uq_event_citizen_report"),)

    event_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("emergency_events.id", ondelete="CASCADE"), index=True)
    citizen_report_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("citizen_reports.id", ondelete="CASCADE"), index=True)
    association_type: Mapped[str] = mapped_column(String(32), default="AUTOMATIC")
    association_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    distance_meters: Mapped[float | None] = mapped_column(Float)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    linked_by: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    is_primary_evidence: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    event: Mapped[EmergencyEvent] = relationship(back_populates="reports")


class EventSource(UUIDPrimaryKey, Base):
    __tablename__ = "event_sources"
    event_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("emergency_events.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("official_sources.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), default="external")
    title: Mapped[str | None] = mapped_column(String(400))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    url: Mapped[str | None] = mapped_column(String(600))
    summary: Mapped[str | None] = mapped_column(Text)
    is_official: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    fingerprint: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    event: Mapped[EmergencyEvent] = relationship(back_populates="sources")


class ReportValidation(UUIDPrimaryKey, Timestamped, Base):
    """§21.3: cada decisión queda auditada con validador, fecha, motivo y evidencia."""

    __tablename__ = "report_validations"

    report_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("citizen_reports.id", ondelete="CASCADE"), index=True
    )
    validator_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    decision: Mapped[ReportState] = mapped_column(report_state_enum, nullable=False)
    motivo: Mapped[str | None] = mapped_column(Text)
    evidencia_url: Mapped[str | None] = mapped_column(String(600))
    comentario: Mapped[str | None] = mapped_column(Text)

    report: Mapped[CitizenReport] = relationship(back_populates="validations")


class Resource(UUIDPrimaryKey, Timestamped, Base):
    """Refugios, centros de salud y puntos de apoyo (§22).

    Solo el operador municipal los registra (§6). Un destino no validado
    provoca descarte duro de la ruta (§20.2), así que `validado` no es un
    adorno: decide si una ruta puede terminar aquí.
    """

    __tablename__ = "resources"

    tipo: Mapped[str] = mapped_column(String(64), index=True)
    nombre: Mapped[str] = mapped_column(String(240), nullable=False)
    geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=SRID, spatial_index=True), nullable=False
    )
    direccion: Mapped[str | None] = mapped_column(String(300))
    distrito: Mapped[str | None] = mapped_column(String(120), index=True)
    telefono: Mapped[str | None] = mapped_column(String(40))
    capacidad: Mapped[int | None] = mapped_column(Integer)
    disponible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    acepta_mascotas: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    accesible_movilidad_reducida: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    validado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    # §6: el registro de recursos es del operador municipal. Los importados de
    # OpenStreetMap acreditan que el establecimiento existe y dónde está, no que
    # la municipalidad lo haya designado ni que esté disponible. Se marcan para
    # poder declararlo al ciudadano y para saber cuáles sustituir con el
    # registro municipal antes del piloto (§23, RF-17).
    origen_osm: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    registrado_por_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    actualizado_en_origen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
