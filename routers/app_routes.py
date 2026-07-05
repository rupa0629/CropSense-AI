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
    save_prediction_feedback,
    enqueue_agronomist_review,
    get_dashboard_counts,
    get_recent_analysis,
    list_users,
    list_agronomist_reviews,
    complete_agronomist_review,
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


class PredictionFeedbackPayload(BaseModel):
    is_correct: bool
    corrected_disease: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=1000)


class AgronomistReviewPayload(BaseModel):
    status: str = Field(pattern="^(approved|rejected|needs_more_information)$")
    notes: str = Field(min_length=3, max_length=2000)


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
    crop_stage: str | None = Form(default=None, max_length=80),
    symptom_notes: str | None = Form(default=None, max_length=1000),
    symptoms_confirmed: bool = Form(default=False),
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

    if not symptoms_confirmed:
        fr = {
            "immediate_action": "Confirm visible symptoms before making a treatment decision.",
            "fertiliser": [
                "Compare the predicted disease with the symptom checklist.",
                "Retake a whole-plant or field-pattern photo if symptoms do not match.",
            ],
            "pesticide": [],
            "cultural": [],
            "prevention": [],
            "disease": dr["disease"],
        }

    analysis_id = save_analysis_log(
        user_id=int(user["id"]),
        image_name=image.filename or "uploaded_image",
        disease=dr["disease"],
        confidence=float(dr["confidence"]),
        severity=sr["level"],
        immediate_action=fr.get("immediate_action", ""),
    )

    escalation_reasons: list[str] = []
    if dr.get("needs_retake") or float(dr.get("confidence", 0)) < 0.60:
        escalation_reasons.append("uncertain prediction")
    if sr.get("level") == "Severe":
        escalation_reasons.append("severe symptoms")
    if not symptoms_confirmed:
        escalation_reasons.append("symptoms not confirmed")

    requires_agronomist_review = bool(escalation_reasons)
    if requires_agronomist_review:
        enqueue_agronomist_review(
            analysis_id=analysis_id,
            user_id=int(user["id"]),
            reason=", ".join(escalation_reasons),
            crop_stage=crop_stage,
            symptom_notes=symptom_notes,
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
        "analysis_id": analysis_id,
        "disease": dr,
        "severity": sr,
        "fertilizer": fr,
        "weather": weather_context,
        "location_advisories": location_advisories,
        "symptoms_confirmed": symptoms_confirmed,
        "requires_agronomist_review": requires_agronomist_review,
        "review_reasons": escalation_reasons,
    }


@router.post("/predictions/{analysis_id}/feedback")
def prediction_feedback(
    analysis_id: int,
    payload: PredictionFeedbackPayload,
    user: dict = Depends(current_user),
):
    if not payload.is_correct and not payload.corrected_disease:
        raise HTTPException(
            status_code=400,
            detail="Corrected disease is required when the prediction is marked incorrect",
        )
    saved = save_prediction_feedback(
        analysis_id=analysis_id,
        user_id=int(user["id"]),
        is_correct=payload.is_correct,
        corrected_disease=payload.corrected_disease,
        notes=payload.notes,
    )
    if not saved:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return {
        "ok": True,
        "message": "Feedback saved for agronomist and model-quality review.",
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


@router.get("/admin/agronomist-reviews")
def admin_agronomist_reviews(
    status: str = Query(default="pending", pattern="^(pending|approved|rejected|needs_more_information)$"),
    limit: int = Query(default=100, ge=1, le=200),
    admin: dict = Depends(require_admin),
):
    return {
        "ok": True,
        "reviews": list_agronomist_reviews(limit=limit, status=status),
    }


@router.post("/admin/agronomist-reviews/{review_id}")
def review_agronomist_case(
    review_id: int,
    payload: AgronomistReviewPayload,
    admin: dict = Depends(require_admin),
):
    updated = complete_agronomist_review(
        review_id=review_id,
        reviewer_id=int(admin["id"]),
        status=payload.status,
        reviewer_notes=payload.notes,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Pending review not found")
    return {"ok": True, "message": "Review decision recorded"}
