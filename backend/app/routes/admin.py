from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.auth.service import AuthService
from app.core.database import get_db
from app.core.security import encryption_manager
from app.models.auth import User, BrokerCredential, RefreshToken
from app.models.trading import (
    Order,
    Position,
    Strategy,
    BacktestResult,
    TradeReport,
)

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminUserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    mobile: Optional[str] = None
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None
    is_email_verified: Optional[bool] = None
    is_mobile_verified: Optional[bool] = None
    password: Optional[str] = None


def _require_admin(current_user: User) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


def _serialize_model(instance, exclude_fields: Optional[set] = None) -> dict:
    exclude_fields = exclude_fields or set()
    data = {}
    for column in instance.__table__.columns:  # type: ignore[attr-defined]
        name = column.name
        if name in exclude_fields:
            continue
        value = getattr(instance, name)
        if isinstance(value, (datetime, date)):
            data[name] = value.isoformat()
        else:
            data[name] = value
    return data


@router.get("/overview")
async def get_database_snapshot(
    db: Session = Depends(get_db),
    current_user: User = Depends(AuthService.get_current_user),
):
    _require_admin(current_user)

    return {
        "users": [
            _serialize_model(
                user,
                exclude_fields={
                    "hashed_password",
                    "otp_code",
                    "otp_expires_at",
                    "last_otp_sent_at",
                },
            )
            for user in db.query(User).all()
        ],
        "brokers": [
            _serialize_model(
                broker,
                exclude_fields={"api_key", "api_secret", "refresh_token"},
            )
            for broker in db.query(BrokerCredential).all()
        ],
        "orders": [_serialize_model(order) for order in db.query(Order).all()],
        "positions": [
            _serialize_model(position) for position in db.query(Position).all()
        ],
        "strategies": [
            _serialize_model(strategy) for strategy in db.query(Strategy).all()
        ],
        "backtests": [
            _serialize_model(result) for result in db.query(BacktestResult).all()
        ],
        "trade_reports": [
            _serialize_model(report) for report in db.query(TradeReport).all()
        ],
        "refresh_tokens": [
            _serialize_model(token) for token in db.query(RefreshToken).all()
        ],
    }


@router.patch("/users/{user_id}")
async def update_user_permissions(
    user_id: int,
    payload: AdminUserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(AuthService.get_current_user),
):
    _require_admin(current_user)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    changed = False
    if payload.username is not None:
        user.username = payload.username
        changed = True
    if payload.email is not None:
        user.email = payload.email
        changed = True
    if payload.mobile is not None:
        user.mobile = payload.mobile
        changed = True
    if payload.is_admin is not None:
        user.is_admin = payload.is_admin
        changed = True
    if payload.is_active is not None:
        user.is_active = payload.is_active
        changed = True
    if payload.is_email_verified is not None:
        user.is_email_verified = payload.is_email_verified
        changed = True
    if payload.is_mobile_verified is not None:
        user.is_mobile_verified = payload.is_mobile_verified
        changed = True
    if payload.password:
        user.hashed_password = encryption_manager.hash_password(payload.password)
        changed = True

    if changed:
        db.commit()
        db.refresh(user)

    return _serialize_model(
        user,
        exclude_fields={
            "hashed_password",
            "otp_code",
            "otp_expires_at",
            "last_otp_sent_at",
        },
    )


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(AuthService.get_current_user),
):
    _require_admin(current_user)

    if current_user.id == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete the logged-in admin")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    db.delete(user)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
