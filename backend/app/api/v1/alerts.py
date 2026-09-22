import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.db import get_db
from app.models import Alert, User
from app.schemas import AlertSeverity, AlertStatus, UserRole
from app.schemas.alert import AlertOut, AlertUpdate, RiskProfileOut
from app.services.alert_service import get_risk_profile, list_alerts, update_alert

router = APIRouter(tags=["alerts"])


@router.get("/alerts", response_model=list[AlertOut])
def alerts(
    status: AlertStatus | None = None,
    severity: AlertSeverity | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN)),
):
    return list_alerts(db, status, severity, limit, offset)


@router.get("/alerts/{alert_id}", response_model=AlertOut)
def alert_detail(
    alert_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN)),
):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.patch("/alerts/{alert_id}", response_model=AlertOut)
def update_alert_endpoint(
    alert_id: uuid.UUID,
    req: AlertUpdate,
    user: User = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    if req.status is not None:
        return update_alert(db, user, alert, req.status, req.resolution_reason)
    return alert


@router.get("/risk-profiles/{user_id}", response_model=RiskProfileOut)
def risk_profile(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN)),
):
    profile = get_risk_profile(db, user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Risk profile not found")
    return profile