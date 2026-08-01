"""Fuentes oficiales, salud de fuentes y documentos del RAG (§11, §19)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from geoalchemy2 import Geometry
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.domain import HazardType, SourceKind, SourceStatus
from app.models.base import SRID, Base, Timestamped, UUIDPrimaryKey
from app.models.enums_sa import hazard_type_enum, source_kind_enum, source_status_enum


class OfficialSource(UUIDPrimaryKey, Timestamped, Base):
    """§11.4: toda fuente citada debe tener institución, URL, fecha, hora de
    consulta, ámbito geográfico, vigencia y tipo de información.

    Si falta fecha o vigencia se usa solo como orientación general y así se
    declara: eso lo decide `puede_citarse_como_vigente`.
    """

    __tablename__ = "official_sources"

    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    institucion: Mapped[str] = mapped_column(String(160), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    # Endpoint del healthcheck del §11.3, si la fuente tiene API.
    healthcheck_url: Mapped[str | None] = mapped_column(String(500))
    kind: Mapped[SourceKind] = mapped_column(source_kind_enum)
    ambito_geografico: Mapped[str | None] = mapped_column(String(160))
    tipo_informacion: Mapped[str | None] = mapped_column(String(160))
    # §11.1: hay fuentes confirmadas y fuentes por verificar. Una fuente sin
    # verificar no se cita como confirmada.
    verificada: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    activa: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Vigencia por defecto del dato que entrega esta fuente.
    vigencia_horas: Mapped[int | None] = mapped_column(Integer)
    # Hash del esquema observado la última vez, para detectar cambios (§11.3).
    schema_hash: Mapped[str | None] = mapped_column(String(64))
    ultimo_estado: Mapped[SourceStatus] = mapped_column(
        source_status_enum, default=SourceStatus.OK, nullable=False
    )
    ultima_consulta_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    checks: Mapped[list[SourceHealth]] = relationship(back_populates="source")

    def puede_citarse_como_vigente(self, ahora: datetime) -> bool:
        """§11.3 + §11.4. Se cita como vigente solo si respondió y no venció.

        Una fuente `CAIDO` no se cita en absoluto: el §11.3 dice que se declara
        la ausencia, y el §12 prohíbe presentar silencio como ausencia de
        peligro.
        """
        if self.ultimo_estado in (SourceStatus.CAIDO, SourceStatus.OBSOLETO):
            return False
        if self.ultima_consulta_at is None or self.vigencia_horas is None:
            return False
        return ahora - self.ultima_consulta_at <= timedelta(hours=self.vigencia_horas)


class SourceHealth(UUIDPrimaryKey, Base):
    """Una ejecución del healthcheck del §11.3.

    Se conserva el histórico, no solo el último estado: para explicar una ruta
    pasada (§23) hace falta saber qué fuentes estaban vivas en ese momento.
    """

    __tablename__ = "source_health"

    source_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("official_sources.id", ondelete="CASCADE"), index=True
    )
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    http_status: Mapped[int | None] = mapped_column(Integer)
    latencia_ms: Mapped[float | None] = mapped_column(Float)
    current_version: Mapped[str | None] = mapped_column(String(32))
    feature_count: Mapped[int | None] = mapped_column(Integer)
    schema_hash: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[SourceStatus] = mapped_column(source_status_enum)
    detalle: Mapped[str | None] = mapped_column(Text)

    source: Mapped[OfficialSource] = relationship(back_populates="checks")


class Document(UUIDPrimaryKey, Timestamped, Base):
    """Documento oficial ingerido (§19).

    §12: todo contenido oficial ingerido se almacena con hash y URL de origen,
    y la respuesta cita ambos. Sin eso no hay defensa contra la suplantación
    descrita en el §12.
    """

    __tablename__ = "documents"

    source_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("official_sources.id", ondelete="SET NULL"), index=True
    )
    titulo: Mapped[str] = mapped_column(String(400), nullable=False)
    url_origen: Mapped[str | None] = mapped_column(String(600))
    sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(80))
    coleccion: Mapped[str | None] = mapped_column(String(64), index=True)
    hazard_type: Mapped[HazardType | None] = mapped_column(hazard_type_enum)
    # §19: la ingesta documental extrae número, fecha, nivel, zona, inicio y fin.
    numero: Mapped[str | None] = mapped_column(String(120))
    nivel: Mapped[str | None] = mapped_column(String(64))
    zona: Mapped[str | None] = mapped_column(String(240))
    vigencia_inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    vigencia_fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # §19: se marca como pendiente cuando el formato de origen cambia. No se
    # descarta ni se adivina: se marca y una persona lo revisa.
    extraccion_pendiente: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    texto_completo: Mapped[str | None] = mapped_column(Text)
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(UUIDPrimaryKey, Base):
    """Fragmento indexado para el RAG (§19).

    La dimensión del vector la fija el modelo de embeddings configurado
    (nomic-embed-text-v1.5 → 768). Cambiar de modelo obliga a reindexar; por
    eso la dimensión sale de `settings` y no de una constante suelta.
    """

    __tablename__ = "document_chunks"
    __table_args__ = (
        Index(
            "ix_document_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index(
            "ix_document_chunks_trgm",
            "texto",
            postgresql_using="gin",
            postgresql_ops={"texto": "gin_trgm_ops"},
        ),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(settings.embedding_dim))
    coleccion: Mapped[str | None] = mapped_column(String(64), index=True)
    hazard_type: Mapped[HazardType | None] = mapped_column(hazard_type_enum)
    region: Mapped[str | None] = mapped_column(String(120), index=True)
    vigencia_fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    # Ámbito geográfico del fragmento, si lo tiene: permite filtrar por región
    # con PostGIS en vez de por coincidencia de texto.
    geom: Mapped[object | None] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=SRID, spatial_index=True)
    )
    metadatos: Mapped[dict | None] = mapped_column(JSONB)

    document: Mapped[Document] = relationship(back_populates="chunks")
