import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.kafka import publish_event
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import RiskProfile, User
from app.schemas.auth import (
    LoginRequest,
    PasswordChange,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.services.audit_service import record_audit

router = APIRouter(tags=["auth"])


@router.post("/auth/register", response_model=TokenResponse, status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.execute(select(User).where(User.email == str(req.email))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")
    if db.execute(select(User).where(User.username == req.username)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already taken")

    user = User(
        email=str(req.email),
        username=req.username,
        full_name=req.full_name,
        password_hash=hash_password(req.password),
    )
    db.add(user)
    db.flush()
    db.add(RiskProfile(user_id=user.id))
    record_audit(db, user, "user.registered", "user", str(user.id))
    db.commit()
    db.refresh(user)

    return {
        "access_token": create_access_token(str(user.id), user.role.value),
        "refresh_token": create_refresh_token(str(user.id), user.role.value),
        "user": user,
    }


@router.post("/auth/login", response_model=TokenResponse)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.username == req.username)).scalar_one_or_none()
    if user is None or not verify_password(req.password, user.password_hash):
        record_audit(db, None, "auth.login_failed", "user", req.username, ip_address=request.client.host)
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    user.last_login_at = datetime.now(timezone.utc)
    record_audit(db, user, "auth.login", "user", str(user.id), ip_address=request.client.host)
    db.commit()

    return {
        "access_token": create_access_token(str(user.id), user.role.value),
        "refresh_token": create_refresh_token(str(user.id), user.role.value),
        "user": user,
    }


@router.post("/auth/refresh", response_model=dict)
def refresh(req: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_token(req.refresh_token)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")
    user = db.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User invalid")
    return {
        "access_token": create_access_token(str(user.id), user.role.value),
        "refresh_token": create_refresh_token(str(user.id), user.role.value),
    }


@router.patch("/auth/password")
def change_password(req: PasswordChange, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(req.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password incorrect")
    user.password_hash = hash_password(req.new_password)
    db.add(user)
    record_audit(db, user, "auth.password_changed", "user", str(user.id))
    db.commit()
    return {"status": "ok"}


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user