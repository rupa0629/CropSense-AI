import io
from PIL import Image
import pytest

from services import model_service


def test_initialize_and_is_initialized(monkeypatch):
    # prevent heavy TensorFlow initialization by stubbing disease_model functions
    monkeypatch.setattr('models.disease_model.configure_tensorflow', lambda **kw: None)
    monkeypatch.setattr('models.disease_model.initialize_models', lambda: None)
    monkeypatch.setattr('models.disease_model.has_custom_model', lambda: True)
    monkeypatch.setattr('models.disease_model.has_backbone', lambda: False)

    model_service.initialize_model()
    assert model_service.is_initialized() is True


def test_predict_monkeypatched(monkeypatch):
    # ensure service reports initialized so it doesn't try to load TF
    monkeypatch.setattr(model_service, '_initialized', True)

    # monkeypatch the underlying model predict to a fast stub
    def fake_predict(image):
        return {"disease": "test-disease", "confidence": 0.88}

    monkeypatch.setattr('models.disease_model.predict_disease', fake_predict)

    img = Image.new("RGB", (32, 32), color=(255, 0, 0))
    res = model_service.predict_disease(img)
    assert res["disease"] == "test-disease"
    assert 0.0 <= res["confidence"] <= 1.0
