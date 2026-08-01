"""Agrupación determinista de reportes; no depende del modelo generativo."""
from __future__ import annotations

from difflib import SequenceMatcher
from datetime import timedelta

from geoalchemy2 import Geography
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import CitizenReport, EmergencyEvent, EventCitizenReport
from app.models.base import SRID

GEOGRAPHY = Geography(srid=SRID)


def text_similarity(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, " ".join(a.lower().split()), " ".join(b.lower().split())).ratio()


def find_or_create_event(session: Session, report: CitizenReport) -> tuple[EmergencyEvent, float]:
    lat = session.scalar(select(func.ST_Y(report.geom)))
    lon = session.scalar(select(func.ST_X(report.geom)))
    point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), SRID)
    candidates = session.scalars(select(EmergencyEvent).where(
        EmergencyEvent.tipo == report.tipo,
        EmergencyEvent.last_reported_at >= report.reportado_at - timedelta(hours=settings.citizen_report_group_time_hours),
        EmergencyEvent.last_reported_at <= report.reportado_at + timedelta(hours=settings.citizen_report_group_time_hours),
        func.ST_DWithin(EmergencyEvent.geom.cast(GEOGRAPHY), cast(point, GEOGRAPHY), settings.citizen_report_group_radius_meters),
    )).all()
    best = None
    best_score = 0.0
    for event in candidates:
        distance = session.scalar(select(func.ST_Distance(event.geom.cast(GEOGRAPHY), cast(point, GEOGRAPHY)))) or 0.0
        similarity = text_similarity(report.descripcion, event.resumen)
        geographic = max(0.0, 1.0 - distance / settings.citizen_report_group_radius_meters)
        score = max(similarity, geographic)
        if score >= settings.citizen_report_min_text_similarity and score > best_score:
            best, best_score = event, score
    if best is None:
        best = EmergencyEvent(tipo=report.tipo, titulo=(report.descripcion or report.tipo.value).strip()[:400],
                              resumen=report.descripcion, distrito=report.distrito,
                              geom=from_shape(Point(lon, lat), srid=SRID), first_reported_at=report.reportado_at,
                              last_reported_at=report.reportado_at)
        session.add(best)
        session.flush()
        best_score = 1.0
    return best, best_score


def attach_report(session: Session, event: EmergencyEvent, report: CitizenReport, confidence: float) -> None:
    if not session.scalar(select(EventCitizenReport).where(EventCitizenReport.event_id == event.id, EventCitizenReport.citizen_report_id == report.id)):
        session.add(EventCitizenReport(event_id=event.id, citizen_report_id=report.id,
                                       association_confidence=confidence, is_primary_evidence=True))
    event.first_reported_at = min(event.first_reported_at or report.reportado_at, report.reportado_at)
    event.last_reported_at = max(event.last_reported_at or report.reportado_at, report.reportado_at)
    event.resumen = event.resumen or report.descripcion
    event.distrito = event.distrito or report.distrito
    # Aporte ciudadano acotado: nunca basta para declarar confirmación oficial.
    linked = list(session.scalars(select(CitizenReport).join(EventCitizenReport).where(EventCitizenReport.event_id == event.id)))
    unique_people = len({r.reporter_key_hash or str(r.id) for r in linked})
    event.confianza = min(20.0, 5.0 if unique_people == 1 else 10.0 if unique_people < 10 else 15.0 if unique_people < 20 else 20.0)
    event.estado_validacion = "SIN_CONFIRMAR"
    session.flush()
