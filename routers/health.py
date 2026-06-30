from fastapi import APIRouter
from fastapi.responses import JSONResponse
from services import model_service
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
def health():
    return {"ok": True, "service": "cropsense-api"}


@router.get("/health/live")
def liveness():
    return JSONResponse(status_code=200, content={"live": True})


@router.get("/health/ready")
def readiness():
    try:
        ready = model_service.is_initialized()
        status = 200 if ready else 503
        return JSONResponse(status_code=status, content={"ready": ready})
    except Exception:
        logger.exception("Readiness check failed")
        return JSONResponse(status_code=500, content={"ready": False})
