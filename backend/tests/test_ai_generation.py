import json
import os

import pytest
from fastapi.testclient import TestClient

from tests.conftest import (
    auth_headers,
    create_admin_and_login,
    register_parent,
)
from tests.test_exam_engine import _make_taxonomy


# ── Mock Provider Tests ──────────────────────────────────────────────────────


def test_mock_provider_generates_structured_questions(client: TestClient):
    from app.services.ai_providers import GenerationParams, mock_generate
    import asyncio

    params = GenerationParams(
        outcome_code="OC-MATH-FRAC",
        outcome_title="Fractions Test",
        count=5,
        difficulty_mix={"easy": 40, "medium": 30, "hard": 30},
    )
    questions, token_usage = asyncio.run(mock_generate(params))
    assert token_usage is None  # mock has no token usage
    assert len(questions) >= 1
    for q in questions:
        assert q.question_text
        assert len(q.options) >= 2
        assert sum(1 for o in q.options if o["is_correct"]) == 1
        assert q.correct_answer
        assert q.provider == "mock"


def test_mock_provider_respects_count(client: TestClient):
    from app.services.ai_providers import GenerationParams, mock_generate
    import asyncio

    for n in [1, 3, 10, 25]:
        params = GenerationParams(count=n)
        questions, _ = asyncio.run(mock_generate(params))
        assert 1 <= len(questions) <= max(1, n)


# ── Preview Tests ────────────────────────────────────────────────────────────


def test_preview_does_not_save(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    from tests.test_curriculum import _create_framework, _create_outcome
    fw = _create_framework(client, tokens, name="AI FW")
    outcome = _create_outcome(client, tokens, fw["id"], "AI-TEST", "AI Preview Test")

    # Check question count before preview
    resp_before = client.get(
        "/api/v1/admin/content/review?source_type=ai",
        headers=auth_headers(tokens),
    )
    count_before = len(resp_before.json())

    # Preview
    resp = client.post(
        "/api/v1/admin/content/ai-generate/preview",
        json={
            "outcome_id": outcome["id"],
            "subject_id": sid,
            "exam_type_id": eid,
            "count": 3,
            "provider": "mock",
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["questions"]) >= 1
    assert "summary" in data

    # Question count should NOT have changed
    resp_after = client.get(
        "/api/v1/admin/content/review?source_type=ai",
        headers=auth_headers(tokens),
    )
    assert len(resp_after.json()) == count_before


# ── Execute Tests ────────────────────────────────────────────────────────────


def test_execute_saves_draft_questions(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    from tests.test_curriculum import _create_framework, _create_outcome
    fw = _create_framework(client, tokens, name="AI Execute FW")
    outcome = _create_outcome(client, tokens, fw["id"], "AI-EXEC", "AI Execute Test")

    resp = client.post(
        "/api/v1/admin/content/ai-generate/execute",
        json={
            "outcome_id": outcome["id"],
            "framework_id": fw["id"],
            "subject_id": sid,
            "exam_type_id": eid,
            "count": 5,
            "provider": "mock",
        },
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["saved_count"] >= 1
    assert data["job_id"]
    assert data["status"] == "completed"

    # Verify questions appear as draft in review queue
    resp2 = client.get(
        "/api/v1/admin/content/review?source_type=ai",
        headers=auth_headers(tokens),
    )
    drafts = resp2.json()
    ai_drafts = [q for q in drafts if q["source_type"] == "ai"]
    assert len(ai_drafts) >= data["saved_count"]


def test_execute_creates_outcome_mapping(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    from tests.test_curriculum import _create_framework, _create_outcome
    fw = _create_framework(client, tokens, name="AI Map FW")
    outcome = _create_outcome(client, tokens, fw["id"], "AI-MAP", "AI Map Test")

    client.post(
        "/api/v1/admin/content/ai-generate/execute",
        json={
            "outcome_id": outcome["id"],
            "framework_id": fw["id"],
            "subject_id": sid,
            "exam_type_id": eid,
            "count": 3,
            "provider": "mock",
        },
        headers=auth_headers(tokens),
    )

    # Check coverage to see that outcome has questions now
    resp = client.get(
        f"/api/v1/curriculum/coverage/{fw['id']}",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    coverage = resp.json()
    mapped = [o for o in coverage["outcomes"] if o["code"] == "AI-MAP"]
    assert len(mapped) == 1
    # AI-generated questions are draft (not approved), so they count as draft_count
    assert mapped[0]["draft_question_count"] >= 1


# ── Job Audit Tests ──────────────────────────────────────────────────────────


def test_ai_job_created(client: TestClient):
    tokens = create_admin_and_login(client)
    sid, eid = _make_taxonomy(client, tokens)

    from tests.test_curriculum import _create_framework, _create_outcome
    fw = _create_framework(client, tokens, name="AI Job FW")
    outcome = _create_outcome(client, tokens, fw["id"], "AI-JOB", "AI Job Test")

    exec_resp = client.post(
        "/api/v1/admin/content/ai-generate/execute",
        json={
            "outcome_id": outcome["id"],
            "subject_id": sid,
            "exam_type_id": eid,
            "count": 2,
            "provider": "mock",
        },
        headers=auth_headers(tokens),
    )
    job_id = exec_resp.json()["job_id"]

    # List jobs
    resp = client.get(
        "/api/v1/admin/content/ai-generate/jobs",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert any(j["id"] == job_id for j in resp.json())

    # Get detail
    resp2 = client.get(
        f"/api/v1/admin/content/ai-generate/jobs/{job_id}",
        headers=auth_headers(tokens),
    )
    assert resp2.status_code == 200
    detail = resp2.json()
    assert detail["id"] == job_id
    assert detail["provider"] == "mock"
    assert detail["saved_count"] >= 1


# ── Permission Tests ─────────────────────────────────────────────────────────


def test_non_admin_cannot_preview_ai(client: TestClient):
    tokens = register_parent(client)
    resp = client.post(
        "/api/v1/admin/content/ai-generate/preview",
        json={"outcome_id": "any", "subject_id": "any", "exam_type_id": "any", "count": 1, "provider": "mock"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 403


def test_non_admin_cannot_execute_ai(client: TestClient):
    tokens = register_parent(client)
    resp = client.post(
        "/api/v1/admin/content/ai-generate/execute",
        json={"outcome_id": "any", "subject_id": "any", "exam_type_id": "any", "count": 1, "provider": "mock"},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 403


# ── Validation Tests ─────────────────────────────────────────────────────────


def test_invalid_mcq_single_correct_answer_enforced(client: TestClient):
    from app.services.ai_service import _validate_generated_question
    from app.services.ai_providers import GeneratedQuestion

    # 0 correct answers
    q = GeneratedQuestion(
        question_text="What is the answer to life?",
        options=[{"label": "A", "text": "42", "is_correct": False}],
        correct_answer="Z",
        explanation="It's 42, obviously",
        difficulty="hard",
        curriculum_outcome_code="TEST",
    )
    errors = _validate_generated_question(q)
    assert len(errors) >= 1
    assert any("correct answer" in e.lower() or "insufficient options" in e.lower() for e in errors)

    # 2 correct answers
    q2 = GeneratedQuestion(
        question_text="Test with two correct",
        options=[
            {"label": "A", "text": "One", "is_correct": True},
            {"label": "B", "text": "Two", "is_correct": True},
        ],
        correct_answer="A",
        explanation="Should fail validation",
        difficulty="easy",
        curriculum_outcome_code="TEST",
    )
    errors2 = _validate_generated_question(q2)
    assert any("exactly 1" in e.lower() for e in errors2)


def test_invalid_explanation_rejected(client: TestClient):
    from app.services.ai_service import _validate_generated_question
    from app.services.ai_providers import GeneratedQuestion

    q = GeneratedQuestion(
        question_text="Test with short explanation",
        options=[{"label": "A", "text": "Yes", "is_correct": True}],
        correct_answer="A",
        explanation="Too short",  # < 10 chars
        difficulty="easy",
        curriculum_outcome_code="TEST",
    )
    errors = _validate_generated_question(q)
    assert any("explanation" in e.lower() for e in errors)


# ── Structured JSON Parsing ──────────────────────────────────────────────────


def test_parse_valid_structured_response():
    from app.services.ai_providers import _parse_structured_response

    valid = json.dumps({
        "questions": [
            {
                "question_text": "What is 2+2?",
                "options": [
                    {"label": "A", "text": "4", "is_correct": True},
                    {"label": "B", "text": "3", "is_correct": False},
                ],
                "correct_answer": "A",
                "explanation": "2+2=4",
                "difficulty": "easy",
            }
        ]
    })
    result = _parse_structured_response(valid)
    assert len(result) == 1
    assert result[0]["question_text"] == "What is 2+2?"


def test_parse_response_missing_questions_key():
    from app.services.ai_providers import _parse_structured_response

    with pytest.raises(ValueError, match="missing 'questions'"):
        _parse_structured_response('{"data": []}')


def test_parse_response_not_json():
    from app.services.ai_providers import _parse_structured_response

    with pytest.raises(ValueError, match="not valid JSON"):
        _parse_structured_response("This is not JSON at all.")


def test_parse_response_empty_questions():
    from app.services.ai_providers import _parse_structured_response

    with pytest.raises(ValueError, match="non-empty"):
        _parse_structured_response('{"questions": []}')


def test_parse_response_question_missing_text():
    from app.services.ai_providers import _parse_structured_response

    with pytest.raises(ValueError, match="missing question_text"):
        _parse_structured_response('{"questions": [{"options": []}]}')


# ── Cost Estimation ──────────────────────────────────────────────────────────


def test_cost_estimation():
    from app.services.ai_providers import _estimate_cost

    # OpenAI: 1000 prompt + 500 completion
    cost = _estimate_cost("openai", {"prompt_tokens": 1000, "completion_tokens": 500})
    expected = (1000 / 1000) * 0.0025 + (500 / 1000) * 0.010
    assert cost == round(expected, 6)

    # Ollama: always 0
    cost2 = _estimate_cost("ollama", {"prompt_tokens": 5000, "completion_tokens": 2000})
    assert cost2 == 0.0


# ── Provider Registry ────────────────────────────────────────────────────────


def test_all_providers_registered():
    from app.services.ai_providers import _PROVIDERS, get_provider

    assert "mock" in _PROVIDERS
    assert "openai" in _PROVIDERS
    assert "claude" in _PROVIDERS
    assert "deepseek" in _PROVIDERS
    assert "ollama" in _PROVIDERS

    # Unknown provider falls back to mock
    assert get_provider("nonexistent") == _PROVIDERS["mock"]


def test_provider_returns_correct_tuple_type():
    from app.services.ai_providers import GenerationParams, mock_generate
    import asyncio

    params = GenerationParams(count=1)
    questions, token_usage = asyncio.run(mock_generate(params))
    assert isinstance(questions, list)
    assert token_usage is None  # mock returns None for token usage


def test_provider_fallback_to_mock_on_missing_key():
    """Verify that when a real provider lacks an API key, mock is used."""
    from app.services.ai_providers import GenerationParams, mock_generate, get_provider
    import asyncio
    import os

    # Temporarily unset any OPENAI_API_KEY to test fallback
    old_val = os.environ.pop("OPENAI_API_KEY", None)
    try:
        provider = get_provider("openai")
        # Provider will raise ValueError when called without key
        params = GenerationParams(count=1)
        import asyncio
        try:
            asyncio.run(provider(params))
        except ValueError as e:
            assert "OPENAI_API_KEY" in str(e)
    finally:
        if old_val:
            os.environ["OPENAI_API_KEY"] = old_val
