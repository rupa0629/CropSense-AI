from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from datetime import datetime, timezone, timedelta
from typing import Optional
import logging

from config.settings import get_settings
from utils.auth_db import get_user_by_id

settings = get_settings()
security = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


def _decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except JWTError as e:
        logger.debug("Invalid access token: %s", e)
        raise HTTPException(status_code=401, detail="Invalid or expired access token")


def current_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="Authorization required")
    payload = _decode_access_token(creds.credentials)
    uid = int(payload.get("uid", 0))
    user = get_user_by_id(uid)
    if not user:
        raise HTTPException(status_code=401, detail="Token user not found")
    return user


def require_admin(user: dict = Depends(current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user
