"""Modelo de datos del §27.

El orden de importación importa: `enums_sa` primero (tipos ENUM compartidos),
luego las tablas. Importar este paquete registra todo en `Base.metadata`.
"""

from app.models.base import SRID, Base, Timestamped, UUIDPrimaryKey, utcnow
from app.models.enums_sa import (  # noqa: F401  (registra los tipos ENUM)
    channel_enum,
    confidence_enum,
    consent_purpose_enum,
    hazard_type_enum,
    operation_level_enum,
    report_state_enum,
    role_enum,
    source_kind_enum,
    source_status_enum,
    trust_level_enum,
    urgency_enum,
)
from app.models.alerts import Alert, AlertZone, MunicipalNotice
from app.models.assist import (
    Conversation,
    FamilyPlan,
    Incident,
    Message,
    PlanTask,
)
from app.models.community import CitizenReport, EmergencyEvent, EventCitizenReport, EventSource, ReportValidation, Resource
from app.models.geo import AffectedRoad, Hazard, RoadBlock, Route, RouteSegment
from app.models.identity import Consent, HouseholdProfile, User
from app.models.ops import (
    AuditLog,
    EmergencyPhone,
    Protocol,
    RetentionJob,
    RiskParameters,
)
from app.models.sources import Document, DocumentChunk, OfficialSource, SourceHealth

__all__ = [
    "SRID",
    "AffectedRoad",
    "Alert",
    "AlertZone",
    "AuditLog",
    "Base",
    "CitizenReport",
    "EmergencyEvent",
    "EventCitizenReport",
    "EventSource",
    "Consent",
    "Conversation",
    "Document",
    "DocumentChunk",
    "EmergencyPhone",
    "FamilyPlan",
    "Hazard",
    "HouseholdProfile",
    "Incident",
    "Message",
    "MunicipalNotice",
    "OfficialSource",
    "PlanTask",
    "Protocol",
    "ReportValidation",
    "Resource",
    "RetentionJob",
    "RiskParameters",
    "RoadBlock",
    "Route",
    "RouteSegment",
    "SourceHealth",
    "Timestamped",
    "UUIDPrimaryKey",
    "User",
    "utcnow",
]
