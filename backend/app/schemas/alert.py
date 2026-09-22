import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas import AlertSeverity, AlertStatus


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ref_no: str
    account_id: uuid.UUID
    user_id: uuid.UUID | None
    transaction_id: uuid.UUID | None
    severity: AlertSeverity
    status: AlertStatus
    alert_type: str
    rule_code: str | None
    risk_score: int
    description: str
    assignee_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime | None
    resolved_at: datetime | None
    resolution_reason: str | None


class AlertUpdate(BaseModel):
    status: AlertStatus | None = None
    resolution_reason: str | None = None


class AlertAssign(BaseModel):
    assignee_id: uuid.UUID


class RiskProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    risk_level: str
    risk_score_current: int
    failed_attempts_24h: int
    flagged_count_30d: int
    last_event_at: datetime | None
    updated_at: datetime | None
    reviewed_by: str | None
    last_reviewed_at: datetime | None