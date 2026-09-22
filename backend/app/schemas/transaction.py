import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas import TxnChannel, TxnStatus, TxnType


class TxnCreate(BaseModel):
    account_id: uuid.UUID
    txn_type: TxnType
    amount: float = Field(gt=0)
    currency: str = "USD"
    channel: TxnChannel = TxnChannel.WEB
    device_fingerprint: str | None = None
    device_name: str | None = None
    device_type: str | None = None
    os: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    city: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=60)
    ip_address: str | None = Field(default=None, max_length=45)
    metadata: dict | None = None


class TxnFeatureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    amount: float
    transaction_type: str
    account_age_days: int
    txn_count_1h: int
    txn_count_24h: int
    failed_count_24h: int
    amount_sum_1h: float
    previous_amount: float | None
    avg_amount_30d: float | None
    amount_ratio: float | None
    distance_km: float | None
    speed_kmh: float | None
    hour_of_day: int
    is_weekend: bool
    device_is_new: bool
    location_is_new: bool
    normal_hours: bool


class TxnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    txn_ref: str
    account_id: uuid.UUID
    txn_type: TxnType
    amount: float
    currency: str
    status: TxnStatus
    risk_score: int | None
    decision_reason: list | None
    channel: TxnChannel
    city: str | None
    country: str | None
    created_at: datetime
    processed_at: datetime | None
    features: TxnFeatureOut | None = None


class TxnDecision(BaseModel):
    transaction: TxnOut
    risk_score: int
    status: TxnStatus
    decision_reasons: list = Field(default_factory=list)
    ml_probability: float | None = None
    manual: Literal[False] = False


class TxnReviewRequest(BaseModel):
    decision: Literal["approved", "rejected", "flagged"]
    reason: str = ""


class TxnReviewOut(BaseModel):
    transaction: TxnOut
    status: TxnStatus
    override: bool = True