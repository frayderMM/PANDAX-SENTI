"""Peligros, vías afectadas, cierres y rutas (§20).

El reparto del §20.1 se refleja en el esquema:

- `RoadBlock` con geometría puntual o de tramo pequeño → `exclude_locations` /
  `exclude_polygons` en la PETICIÓN a Valhalla.
- `Hazard` con geometría amplia (cuenca inundada, faja marginal, quebrada) →
  filtro PostGIS POSTERIOR sobre la polilínea devuelta.

Mezclar los dos mecanismos es el error que el §20.1 previene: `exclude_polygons`
es costoso por petición y está pensado para áreas pequeñas.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain import ConfidenceLevel, HazardType, TrustLevel
from app.models.base import SRID, Base, Timestamped, UUIDPrimaryKey
from app.models.enums_sa import confidence_enum, hazard_type_enum, trust_level_enum


class Hazard(UUIDPrimaryKey, Timestamped, Base):
    """Zona de peligro amplia (INGEMMET / SIGRID / ANA).

    Se resuelve con filtro PostGIS posterior, no con `exclude_polygons` (§20.1).
    Intersectar una de estas zonas da riesgo 0.70 en el §20.3: penaliza fuerte
    pero no descarta, porque son áreas amplias y no cierres puntuales.
    """

    __tablename__ = "hazards"

    tipo: Mapped[HazardType] = mapped_column(hazard_type_enum, index=True)
    nombre: Mapped[str | None] = mapped_column(String(240))
    fuente: Mapped[str | None] = mapped_column(String(160))
    nivel: Mapped[str | None] = mapped_column(String(64))
    # "alto" es el que dispara el 0.70 del §20.3.
    peligro_alto: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=SRID, spatial_index=True), nullable=False
    )
    vigencia_fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)


class AffectedRoad(UUIDPrimaryKey, Timestamped, Base):
    """Vía con afectación reportada, no necesariamente cerrada."""

    __tablename__ = "affected_roads"

    nombre: Mapped[str | None] = mapped_column(String(240), index=True)
    osm_way_id: Mapped[int | None] = mapped_column(Integer, index=True)
    tipo_afectacion: Mapped[HazardType] = mapped_column(hazard_type_enum)
    geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=SRID, spatial_index=True), nullable=False
    )
    trust_level: Mapped[TrustLevel] = mapped_column(
        trust_level_enum, default=TrustLevel.PENDIENTE, nullable=False
    )
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("citizen_reports.id", ondelete="SET NULL")
    )
    vence_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class RoadBlock(UUIDPrimaryKey, Timestamped, Base):
    """Cierre de vía (§6, §20.1, §21.2).

    Solo el operador municipal o una fuente oficial cierran una vía (§6). Esa
    regla vive en el permiso `CONFIRMAR_CIERRE_VIA` y en `confianza`, que solo
    admite OFICIAL o MUNICIPAL para que el cierre sea vinculante.

    Un cierre vigente provoca DESCARTE DURO de cualquier ruta que lo cruce
    (§20.2) — nunca penalización.
    """

    __tablename__ = "road_blocks"

    nombre_via: Mapped[str | None] = mapped_column(String(240))
    motivo: Mapped[HazardType] = mapped_column(hazard_type_enum)
    descripcion: Mapped[str | None] = mapped_column(Text)

    confianza: Mapped[ConfidenceLevel] = mapped_column(confidence_enum, nullable=False)
    confirmado_por_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("official_sources.id", ondelete="SET NULL")
    )

    # Punto de bloqueo → exclude_locations. Polígono pequeño → exclude_polygons.
    punto: Mapped[object | None] = mapped_column(
        Geometry(geometry_type="POINT", srid=SRID, spatial_index=True)
    )
    poligono: Mapped[object | None] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=SRID, spatial_index=True)
    )

    vigente: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    inicio_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fin_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    reabierto_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def es_vinculante(self) -> bool:
        """§6: solo el operador municipal o una fuente oficial cierran una vía."""
        return self.vigente and self.confianza in (
            ConfidenceLevel.OFICIAL,
            ConfidenceLevel.MUNICIPAL,
        )


class Route(UUIDPrimaryKey, Timestamped, Base):
    """Ruta calculada y entregada (§20.5).

    §23: "una ruta pasada debe poder explicarse con los parámetros vigentes en
    su momento". Por eso se guardan `parametros_version`, `pesos`, los
    subpuntajes y los ids de los bloqueos considerados: no se recalcula la
    explicación después, se conserva.
    """

    __tablename__ = "routes"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL"), index=True
    )

    origen: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=SRID), nullable=False
    )
    destino: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=SRID), nullable=False
    )
    destino_resource_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("resources.id", ondelete="SET NULL")
    )

    costing: Mapped[str] = mapped_column(String(32), nullable=False)
    geometria: Mapped[object | None] = mapped_column(
        Geometry(geometry_type="LINESTRING", srid=SRID, spatial_index=True)
    )
    distancia_m: Mapped[float | None] = mapped_column(Float)
    duracion_s: Mapped[float | None] = mapped_column(Float)

    # §20.3, los cinco subpuntajes normalizados y el total.
    s_seguridad: Mapped[float | None] = mapped_column(Float)
    s_fuente: Mapped[float | None] = mapped_column(Float)
    s_accesible: Mapped[float | None] = mapped_column(Float)
    s_duracion: Mapped[float | None] = mapped_column(Float)
    s_distancia: Mapped[float | None] = mapped_column(Float)
    puntaje: Mapped[float | None] = mapped_column(Float, index=True)

    recomendada: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    descartada: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    motivo_descarte: Mapped[str | None] = mapped_column(Text)
    # §20.5: nivel de confianza mostrado al usuario, y §20.4: si la cartografía
    # de la zona está bajo el umbral, la respuesta cambia de "esta es la ruta" a
    # "esta es una ruta posible".
    nivel_confianza: Mapped[str | None] = mapped_column(String(16))
    cobertura_suficiente: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    parametros_version: Mapped[str | None] = mapped_column(String(32))
    pesos: Mapped[dict | None] = mapped_column(JSONB)
    bloqueos_considerados: Mapped[list | None] = mapped_column(JSONB)
    fuentes_citadas: Mapped[list | None] = mapped_column(JSONB)
    explicacion: Mapped[str | None] = mapped_column(Text)

    segments: Mapped[list[RouteSegment]] = relationship(
        back_populates="route", cascade="all, delete-orphan"
    )


class RouteSegment(UUIDPrimaryKey, Base):
    """Tramo de una ruta con su riesgo (§20.3).

    `S_seguridad = 1 − max(riesgo de cualquier tramo)`. Guardar el riesgo por
    tramo es lo que permite responder "¿por qué esta ruta y no la otra?" sin
    recalcular nada.
    """

    __tablename__ = "route_segments"

    route_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("routes.id", ondelete="CASCADE"), index=True
    )
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    instruccion: Mapped[str | None] = mapped_column(Text)
    distancia_m: Mapped[float | None] = mapped_column(Float)
    geom: Mapped[object | None] = mapped_column(
        Geometry(geometry_type="LINESTRING", srid=SRID)
    )
    riesgo: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    motivo_riesgo: Mapped[str | None] = mapped_column(String(240))
    pendiente_max: Mapped[float | None] = mapped_column(Float)
    tiene_escaleras: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    superficie: Mapped[str | None] = mapped_column(String(40))

    route: Mapped[Route] = relationship(back_populates="segments")
