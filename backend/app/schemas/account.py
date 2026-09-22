import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas import AccountStatus, AccountType


class AccountCreate(BaseModel):
    account_type: AccountType = AccountType.CHECKING
    currency: str = "USD"
    opening_balance: float = Field(ge=0, default=0)


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    account_number: str
    account_type: AccountType
    currency: str
    balance: float
    status: AccountStatus
    opened_at: datetime
    account_age_days: int


class AccountUpdate(BaseModel):
    status: AccountStatus | None = None


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    fingerprint: str
    device_name: str
    device_type: str
    os: str
    is_trusted: bool
    first_seen_at: datetime
    last_seen_at: datetime