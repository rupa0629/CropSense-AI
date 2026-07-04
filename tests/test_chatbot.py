from utils import chatbot


def _fallback(monkeypatch, question, context=None):
    monkeypatch.setattr(chatbot, "_openai_reply", lambda message, context=None: None)
    return chatbot.get_response(question, context or {})


def test_disease_answer_is_structured_and_source_backed(monkeypatch):
    answer = _fallback(monkeypatch, "How should I manage leaf blast?")

    for section in ("Assessment:", "Evidence:", "Actions:", "Safety:", "Sources:"):
        assert section in answer
    assert "screening concern" in answer.lower()
    assert "knowledgebank.irri.org" in answer
    assert "fao.org" in answer


def test_low_confidence_context_prioritizes_retake(monkeypatch):
    answer = _fallback(
        monkeypatch,
        "What should I do?",
        {
            "latest_prediction": {
                "disease": "Bacterial Blight",
                "confidence": 0.42,
                "needs_retake": True,
            },
            "latest_weather": {"humidity": 88, "description": "heavy rain"},
        },
    )

    assert "Retake a clear close-up" in answer
    assert "humidity 88%" in answer
    assert "heavy rain" in answer.lower()


def test_unknown_question_requests_diagnostic_context(monkeypatch):
    answer = _fallback(monkeypatch, "My rice does not look right")

    assert "not enough information" in answer
    assert "growth stage" in answer
    assert "field distribution" in answer


def test_unsafe_request_is_refused(monkeypatch):
    answer = _fallback(monkeypatch, "How can I poison someone?")

    assert "cannot help" in answer
    assert "emergency" in answer


def test_malformed_model_answer_is_rejected():
    assert chatbot._is_well_formed_answer("A confident but unstructured answer") is False
    assert chatbot._is_well_formed_answer(
        "Assessment:\n- A\nEvidence:\n- B\nActions:\n- C\nSafety:\n- D\nSources:\n- E"
    ) is True
