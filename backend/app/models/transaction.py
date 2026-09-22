from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Float,
    Integer,
    Numeric,
    String,
    Text,
    func,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.db import Base
from app.models.enums import TxnChannel, TxnStatus, TxnType


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (UniqueConstraint("txn_ref", name="uq_txn_ref"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    txn_ref: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    txn_type: Mapped[TxnType] = mapped_column(Enum(TxnType, name="txn_type"))
    amount: Mapped[float] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    status: Mapped[TxnStatus] = mapped_column(
        Enum(TxnStatus, name="txn_status"), default=TxnStatus.PENDING, index=True
    )
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    decision_reason: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    channel: Mapped[TxnChannel] = mapped_column(
        Enum(TxnChannel, name="txn_channel"), default=TxnChannel.WEB
    )
    device_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("devices.id"), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(60), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    extra_data: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    account: Mapped["Account"] = relationship(back_populates="transactions")
    device: Mapped["Device | None"] = relationship()
    features: Mapped["TxnFeature | None"] = relationship(back_populates="transaction", uselist=False)
    ml_score: Mapped["MLScore | None"] = relationship(back_populates="transaction", uselist=False)


class TxnFeature(Base):
    __tablename__ = "txn_features"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), unique=True
    )
    amount: Mapped[float] = mapped_column(Float)
    transaction_type: Mapped[str] = mapped_column(String(20))
    account_age_days: Mapped[int] = mapped_column(Integer)
    txn_count_1h: Mapped[int] = mapped_column(Integer, default=0)
    txn_count_24h: Mapped[int] = mapped_column(Integer, default=0)
    failed_count_24h: Mapped[int] = mapped_column(Integer, default=0)
    amount_sum_1h: Mapped[float] = mapped_column(Float, default=0)
    previous_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_amount_30d: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    speed_kmh: Mapped[float | None] = mapped_column(Float, nullable=True)
    hour_of_day: Mapped[int] = mapped_column(Integer, default=0)
    is_weekend: Mapped[bool] = mapped_column(Integer, default=0)
    device_is_new: Mapped[bool] = mapped_column(Integer, default=0)
    location_is_new: Mapped[bool] = mapped_column(Integer, default=0)
    normal_hours: Mapped[bool] = mapped_column(Integer, default=1)

    transaction: Mapped["Transaction"] = relationship(back_populates="features")


class MLScore(Base):
    __tablename__ = "ml_scores"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), unique=True
    )
    model_version: Mapped[str] = mapped_column(String(40), default="none")
    fraud_probability: Mapped[float] = mapped_column(Float, default=0.0)
    ml_risk: Mapped[float] = mapped_column(Float, default=0.0)
    shap_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    transaction: Mapped["Transaction"] = relationship(back_populates="ml_score")