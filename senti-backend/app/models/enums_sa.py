"""Tipos ENUM de PostgreSQL, instanciados una sola vez.

Dos `Enum(...)` con el mismo `name` en tablas distintas hacen que `create_all`
intente `CREATE TYPE` dos veces y falle. Se comparte la instancia.

Este módulo no importa nada de `app.models` a propósito: es el nivel más bajo
del paquete y todas las tablas dependen de él.
"""

from __future__ import annotations

from sqlalchemy import Enum

from app.core.security import Role
from app.domain import (
    Channel,
    ConfidenceLevel,
    ConsentPurpose,
    HazardType,
    OperationLevel,
    ReportState,
    SourceKind,
    SourceStatus,
    TrustLevel,
    UrgencyLevel,
)

role_enum = Enum(Role, name="user_role")
consent_purpose_enum = Enum(ConsentPurpose, name="consent_purpose")
confidence_enum = Enum(ConfidenceLevel, name="confidence_level")
urgency_enum = Enum(UrgencyLevel, name="urgency_level")
source_status_enum = Enum(SourceStatus, name="source_status")
source_kind_enum = Enum(SourceKind, name="source_kind")
hazard_type_enum = Enum(HazardType, name="hazard_type")
report_state_enum = Enum(ReportState, name="report_state")
trust_level_enum = Enum(TrustLevel, name="trust_level")
operation_level_enum = Enum(OperationLevel, name="operation_level")
channel_enum = Enum(Channel, name="channel")
