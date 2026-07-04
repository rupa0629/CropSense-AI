from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Query, Form
from pydantic import BaseModel, Field
from PIL import Image
import io
import logging

from config.settings import get_settings
from routers.deps import current_user, require_admin
from services import model_service
from utils.severity import classify_severity
from utils.fertilizer import get_recommendation
from utils.weather import get_weather_advisory
from utils.auth_db import (
    save_analysis_log,
    get_user_settings,
    save_user_settings,
    save_weather_log,
    save_chat_log,
    get_dashboard_counts,
    get_recent_analysis,
    list_users,
    get_admin_overview,
)
from utils.chatbot import get_response

settings = get_settings()
router = APIRouter(tags=["app"])
logger = logging.getLogger(__name__)


class WeatherPayload(BaseModel):
    location: str = Field(default="Delhi,IN", min_length=3, max_length=100)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    api_key: str | None = None
    save_settings: bool = False


class ChatPayload(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    context: dict | None = None


def _validate_image_file(image: UploadFile, data: bytes) -> Image.Image:
    if image.content_type not in settings.allowed_upload_content_types_list:
        raise HTTPException(status_code=400, detail="Unsupported image type")

    if len(data) > settings.max_upload_size_bytes:
        raise HTTPException(status_code=413, detail="Uploaded image exceeds maximum size")

    try:
        pil = Image.open(io.BytesIO(data))
        pil.verify()
    except Exception as exc:
        logger.warning("Image validation failed: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid image file") from exc

    try:
        pil = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as exc:
        logger.warning("Image conversion failed: %s", exc)
        raise HTTPException(status_code=400, detail="Unable to process image") from exc

    return pil


@router.post("/predict")
async def predict(
    image: UploadFile = File(...),
    latitude: float | None = Form(default=None),
    longitude: float | None = Form(default=None),
    user: dict = Depends(current_user),
):
    data = await image.read()
    pil = _validate_image_file(image, data)

    dr = await model_service.predict_disease_async(pil)
    if dr.get("needs_retake"):
        sr = {"level": "Mild", "advice": "Prediction uncertain. Retake clearer close-up image and run analysis again."}
        fr = {"immediate_action": "Retake image before treatment decision.", "fertiliser": ["Capture one leaf clearly in focus"]}
    else:
        sr = classify_severity(dr["disease"], dr["confidence"], pil)
        fr = get_recommendation(dr["disease"], sr["level"])    

    save_analysis_log(
        user_id=int(user["id"]),
        image_name=image.filename or "uploaded_image",
        disease=dr["disease"],
        confidence=float(dr["confidence"]),
        severity=sr["level"],
        immediate_action=fr.get("immediate_action", ""),
    )

    weather_context = None
    location_advisories: list[str] = []
    if latitude is not None and longitude is not None:
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise HTTPException(status_code=400, detail="Invalid location coordinates")

        weather_context = get_weather_advisory(
            location="Photo location",
            latitude=latitude,
            longitude=longitude,
        )
        humidity = float(weather_context.get("humidity", 0))
        wind_speed = float(weather_context.get("wind_speed", 0))
        description = str(weather_context.get("description", "")).lower()

        if dr["disease"] in {"Leaf Blast", "Brown Spot"} and humidity >= 80:
            location_advisories.append(
                "High local humidity may favor fungal disease pressure; increase scouting and reduce prolonged leaf wetness."
            )
        if dr["disease"] == "Bacterial Blight" and (
            humidity >= 70 or any(word in description for word in ("rain", "storm", "shower"))
        ):
            location_advisories.append(
                "Humid or rainy local conditions can favor bacterial blight spread; avoid handling wet plants and improve drainage."
            )
        if any(word in description for word in ("rain", "storm", "shower")):
            location_advisories.append(
                "Rain is present or expected locally; postpone foliar treatment unless the registered product label explicitly allows it."
            )
        if wind_speed >= 5:
            location_advisories.append(
                "Local wind is too strong for reliable spraying; wait for calmer conditions and follow the product label."
            )
        if not location_advisories:
            location_advisories.append(
                "Current local weather does not add a major immediate risk signal; continue field scouting and follow the diagnosis guidance."
            )

    return {
        "ok": True,
        "disease": dr,
        "severity": sr,
        "fertilizer": fr,
        "weather": weather_context,
        "location_advisories": location_advisories,
    }


@router.post("/weather")
def weather(payload: WeatherPayload, user: dict = Depends(current_user)):
    location = payload.location.strip()
    api_key = payload.api_key or None
    save_settings = payload.save_settings

    w = get_weather_advisory(
        location=location,
        api_key=api_key,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    uid = int(user["id"])

    if save_settings:
        existing_settings = get_user_settings(uid)
        save_user_settings(uid, location, api_key or existing_settings.get("weather_api_key", ""))

    save_weather_log(
        user_id=uid,
        location=w["location"],
        temperature=float(w["temperature"]),
        humidity=float(w["humidity"]),
        wind_speed=float(w["wind_speed"]),
        description=w["description"],
        source=w["source"],
    )

    return {"ok": True, "weather": w}


@router.post("/chat")
def chat(payload: ChatPayload, user: dict = Depends(current_user)):
    message = payload.message
    context = payload.context or {}
    reply = get_response(message, context=context)
    uid = int(user["id"])
    save_chat_log(uid, "user", message)
    save_chat_log(uid, "bot", reply)
    return {"ok": True, "reply": reply}


@router.get("/dashboard")
def dashboard(user: dict = Depends(current_user)):
    uid = int(user["id"])
    return {"ok": True, "counts": get_dashboard_counts(uid), "recent": get_recent_analysis(uid, limit=8)}


@router.get("/history")
def history(limit: int = Query(20, le=200), user: dict = Depends(current_user)):
    uid = int(user["id"])
    return {"ok": True, "history": get_recent_analysis(uid, limit=limit)}


@router.get("/admin/overview")
def admin_overview(admin: dict = Depends(require_admin)):
    return {"ok": True, "admin": admin, "overview": get_admin_overview()}


@router.get("/admin/users")
def admin_users(limit: int = 100, admin: dict = Depends(require_admin)):
    return {"ok": True, "users": list_users(limit=limit)}
