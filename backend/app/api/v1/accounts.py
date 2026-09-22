import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import account_belongs_to, get_current_user, require_roles
from app.core.db import get_db
from app.models import Account, Device, User
from app.schemas import AccountStatus, UserRole
from app.schemas.account import AccountCreate, AccountOut, AccountUpdate, DeviceOut
from app.services.audit_service import record_audit

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _account_or_404(db: Session, account_id: uuid.UUID) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.post("", response_model=AccountOut, status_code=201)
def create_account(
    req: AccountCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = Account(
        user_id=user.id,
        account_number=str(uuid.uuid4().int)[:16],
        account_type=req.account_type,
        currency=req.currency,
        balance=req.opening_balance,
    )
    db.add(account)
    db.flush()
    record_audit(db, user, "account.created", "account", str(account.id))
    db.commit()
    db.refresh(account)
    return account


@router.get("", response_model=list[AccountOut])
def list_my_accounts(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    accounts = db.execute(
        select(Account).where(Account.user_id == user.id).order_by(Account.opened_at)
    ).scalars().all()
    return accounts


@router.get("/{account_id}", response_model=AccountOut)
def get_account(
    account_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = _account_or_404(db, account_id)
    if not account_belongs_to(account, user) and user.role not in (UserRole.ADMIN, UserRole.ANALYST):
        raise HTTPException(status_code=403, detail="Forbidden")
    return account


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(
    account_id: uuid.UUID,
    req: AccountUpdate,
    user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    account = _account_or_404(db, account_id)
    if req.status is not None:
        account.status = req.status
    db.add(account)
    record_audit(db, user, "account.updated", "account", str(account.id), {"status": req.status})
    db.commit()
    db.refresh(account)
    return account


@router.get("/{account_id}/devices", response_model=list[DeviceOut])
def list_account_devices(
    account_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = _account_or_404(db, account_id)
    if not account_belongs_to(account, user):
        raise HTTPException(status_code=403, detail="Forbidden")
    return db.execute(select(Device).where(Device.user_id == account.user_id)).scalars().all()