"""Eventos unificados y acciones agregadas sin exponer identidad."""
from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import auditar, db, usuario_actual
from app.models import CitizenReport, EmergencyEvent, EventCitizenReport, EventSource, User

router = APIRouter(prefix="/api/events", tags=["events"])

def _event(session: Session, event_id: str) -> EmergencyEvent:
    event = session.get(EmergencyEvent, event_id)
    if not event:
        raise HTTPException(404, "Evento no encontrado")
    return event

def _reporter_key(user: User) -> str:
    return hashlib.sha256(f"user:{user.id}".encode()).hexdigest()

def _summary(session: Session, event: EmergencyEvent) -> dict:
    reports = list(session.scalars(select(CitizenReport).join(EventCitizenReport).where(EventCitizenReport.event_id == event.id)))
    sources = list(session.scalars(select(EventSource).where(EventSource.event_id == event.id)))
    unique = {r.reporter_key_hash or str(r.id) for r in reports}
    confirmations = sum(1 for r in reports if r.estado.value == "confirmado")
    active = sum(1 for r in reports if r.estado.value not in {"resuelto", "rechazado", "duplicado"})
    resolved = sum(1 for r in reports if r.estado.value == "resuelto")
    lat = session.scalar(select(func.ST_Y(event.geom)))
    lon = session.scalar(select(func.ST_X(event.geom)))
    return {"id": str(event.id), "title": event.titulo, "type": event.tipo.value, "summary": event.resumen,
            "lat": lat, "lon": lon,
            "citizen_report_count": len(reports), "unique_reporter_count": len(unique),
            "external_source_count": len(sources), "official_source_count": sum(s.is_official for s in sources),
            "total_evidence_count": len(reports) + len(sources), "confirmation_count": confirmations,
            "still_active_count": active, "resolved_report_count": resolved,
            "first_reported_at": event.first_reported_at.isoformat() if event.first_reported_at else None,
            "last_reported_at": event.last_reported_at.isoformat() if event.last_reported_at else None,
            "last_verified_at": event.last_verified_at.isoformat() if event.last_verified_at else None,
            "validation_status": event.estado_validacion, "confidence": event.confianza,
            "sources": [_source(s) for s in sources]}

def _source(s: EventSource) -> dict:
    return {"name": s.name, "type": s.source_type, "title": s.title, "published_at": s.published_at.isoformat() if s.published_at else None,
            "is_official": s.is_official, "url": s.url, "available": s.available, "summary": s.summary}

@router.get("")
def list_events(session: Session = Depends(db)) -> dict:
    events = session.scalars(select(EmergencyEvent).order_by(EmergencyEvent.last_reported_at.desc()).limit(200)).all()
    return {"events": [_summary(session, e) for e in events]}

@router.get("/{event_id}")
def detail(event_id: str, session: Session = Depends(db)) -> dict:
    return _summary(session, _event(session, event_id))

@router.get("/{event_id}/citizen-reports")
def citizen_reports(event_id: str, session: Session = Depends(db)) -> dict:
    event = _event(session, event_id)
    rows = session.scalars(select(CitizenReport).join(EventCitizenReport).where(EventCitizenReport.event_id == event.id)).all()
    return {"reports": [{"id": str(r.id), "type": r.tipo.value, "description": r.descripcion, "reported_at": r.reportado_at.isoformat(), "status": r.estado.value, "has_evidence": bool(r.foto_url)} for r in rows]}

@router.get("/{event_id}/sources")
def sources(event_id: str, session: Session = Depends(db)) -> dict:
    event = _event(session, event_id)
    return {"sources": [_source(s) for s in session.scalars(select(EventSource).where(EventSource.event_id == event.id)).all()]}

@router.get("/{event_id}/evidence-summary")
def evidence_summary(event_id: str, session: Session = Depends(db)) -> dict:
    data = _summary(session, _event(session, event_id))
    return {key: data[key] for key in ("total_evidence_count", "citizen_report_count", "external_source_count", "official_source_count", "confirmation_count", "still_active_count", "resolved_report_count")}

class EvidenceIn(BaseModel):
    url: str | None = Field(default=None, max_length=600)
    summary: str | None = Field(default=None, max_length=1000)

def _vote(event_id: str, status: str, request: Request, session: Session, user: User) -> dict:
    event = _event(session, event_id)
    report = session.scalar(select(CitizenReport).where(CitizenReport.reporter_key_hash == _reporter_key(user), CitizenReport.tipo == event.tipo).order_by(CitizenReport.reportado_at.desc()))
    if report is None:
        raise HTTPException(400, "Primero crea un reporte ciudadano para este tipo de evento")
    report.estado = status
    auditar(session, request, actor=user, accion=f"evento.{status}", entidad="emergency_event", entidad_id=event_id, detalle={})
    return _summary(session, event)

@router.post("/{event_id}/confirm")
def confirm(event_id: str, request: Request, session: Session = Depends(db), user: User = Depends(usuario_actual)) -> dict:
    return _vote(event_id, "confirmado", request, session, user)

@router.post("/{event_id}/still-active")
def active(event_id: str, request: Request, session: Session = Depends(db), user: User = Depends(usuario_actual)) -> dict:
    return _vote(event_id, "en_revision", request, session, user)

@router.post("/{event_id}/resolved")
def resolved(event_id: str, request: Request, session: Session = Depends(db), user: User = Depends(usuario_actual)) -> dict:
    return _vote(event_id, "resuelto", request, session, user)

@router.post("/{event_id}/evidence")
def evidence(event_id: str, data: EvidenceIn, request: Request, session: Session = Depends(db), user: User = Depends(usuario_actual)) -> dict:
    event = _event(session, event_id)
    session.add(EventSource(event_id=event.id, name="Reportes ciudadanos", source_type="citizen", title="Evidencia ciudadana", url=data.url, summary=data.summary, is_official=False))
    auditar(session, request, actor=user, accion="evento.evidencia", entidad="emergency_event", entidad_id=event_id, detalle={"tiene_url": bool(data.url)})
    return _summary(session, event)
