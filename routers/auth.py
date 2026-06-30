from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
import logging
import secrets

from routers.deps import current_user
from utils.auth_db import (
    authenticate_user,
    create_password_reset_token,
    create_refresh_token,
    create_user,
    get_user_by_email,
    get_user_by_id,
    mark_password_reset_token_used,
    revoke_all_refresh_tokens_for_user,
    revoke_refresh_token,
    update_user_password,
    validate_password_reset_token,
    validate_refresh_token,
)
from utils.email_service import send_password_reset_email
from config.settings import get_settings

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


class RegisterReq(BaseModel):
    full_name: str
    email: EmailStr
    password: str


class LoginReq(BaseModel):
    email: EmailStr
    password: str


class RefreshReq(BaseModel):
    refresh_token: str


class ForgotPasswordReq(BaseModel):
    email: EmailStr


class ResetPasswordReq(BaseModel):
    reset_token: str
    new_password: str


def _create_access_token(payload: dict) -> str:
    from datetime import datetime, timedelta, timezone
    from jose import jwt

    to_encode = payload.copy()
    to_encode.update({"exp": datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm="HS256")


def _issue_tokens(user: dict) -> dict:
    access_token = _create_access_token(
        {"uid": user["id"], "name": user["full_name"], "email": user["email"], "role": user.get("role", "farmer")} 
    )
    refresh_token = secrets.token_urlsafe(48)
    create_refresh_token(int(user["id"]), refresh_token, expires_minutes=settings.refresh_token_minutes)
    return {"access_token": access_token, "refresh_token": refresh_token}


@router.post("/register")
def register(payload: RegisterReq):
    ok, msg = create_user(payload.full_name, payload.email, payload.password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg}


@router.post("/login")
def login(payload: LoginReq):
    user = authenticate_user(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    tokens = _issue_tokens(user)
    return {"ok": True, "user": user, **tokens}


@router.post("/refresh")
def refresh(payload: RefreshReq):
    token_row = validate_refresh_token(payload.refresh_token)
    if not token_row:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user = get_user_by_id(int(token_row["user_id"]))
    if not user:
        raise HTTPException(status_code=401, detail="Refresh token user not found")

    revoke_refresh_token(payload.refresh_token)
    tokens = _issue_tokens(user)
    return {"ok": True, **tokens}


@router.post("/logout")
def logout(payload: RefreshReq, user: dict = Depends(current_user)):
    revoke_refresh_token(payload.refresh_token)
    return {"ok": True, "message": "Logged out from current session"}


@router.post("/logout-all")
def logout_all(user: dict = Depends(current_user)):
    revoke_all_refresh_tokens_for_user(int(user["id"]))
    return {"ok": True, "message": "All sessions invalidated"}


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordReq):
    user = get_user_by_email(payload.email)
    if not user:
        return {"ok": True, "message": "If account exists, reset instructions were sent."}

    reset_token = secrets.token_urlsafe(36)
    create_password_reset_token(int(user["id"]), reset_token, expires_minutes=30)

    # Send password reset email
    email_sent = send_password_reset_email(payload.email, reset_token)

    if email_sent:
        return {"ok": True, "message": "Password reset instructions sent to your email."}
    logger.error("Password reset email could not be sent for %s", payload.email)
    if settings.environment == "production":
        raise HTTPException(status_code=503, detail="Password reset service is temporarily unavailable")
    return {"ok": True, "message": "Password reset email is unavailable in this environment."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordReq):
    token_row = validate_password_reset_token(payload.reset_token)
    if not token_row:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    ok, msg = update_user_password(int(token_row["user_id"]), payload.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    mark_password_reset_token_used(payload.reset_token)
    revoke_all_refresh_tokens_for_user(int(token_row["user_id"]))
    return {"ok": True, "message": "Password reset successful. Login again."}


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return {"ok": True, "user": user}
