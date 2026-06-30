import io
import pytest
from httpx import ASGITransport, AsyncClient
from api_server import app
from PIL import Image
from utils.auth_db import create_user, get_user_by_email, init_db


@pytest.mark.asyncio
async def test_predict_endpoint(monkeypatch):
    init_db()
    create_user("Integration User", "test@example.com", "StrongPass1!")
    test_user = get_user_by_email("test@example.com")

    # Override auth dependency to bypass token checks
    from routers import deps

    async def fake_user():
        return test_user

    app.dependency_overrides[deps.current_user] = fake_user

    # Stub model prediction to avoid loading TF
    async def fake_predict_async(image):
        return {"disease": "integration-test", "confidence": 0.77}

    monkeypatch.setattr('services.model_service.predict_disease_async', fake_predict_async)

    # Create an in-memory JPEG image for upload
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color=(0, 255, 0)).save(buf, format="JPEG")
    buf.seek(0)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        files = {"image": ("leaf.jpg", buf, "image/jpeg")}
        r = await ac.post("/predict", files=files, headers={})

    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["disease"]["disease"] == "integration-test"




