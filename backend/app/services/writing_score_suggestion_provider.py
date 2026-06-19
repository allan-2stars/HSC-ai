"""M5.4 — AI score suggestion provider. Mock and real providers for rubric scoring.

Provider input: task info, submission content, rubric version dimensions (no student PII).
Provider output: structured dimension suggestions (rating, comment, confidence).
"""
import json
from dataclasses import dataclass, field

import httpx

from app.core.config import settings

PROMPT_VERSION = "wss-v1"


@dataclass
class ScoreSuggestionParams:
    task_title: str = ""
    task_prompt: str = ""
    task_instructions: str = ""
    submission_content: str = ""
    word_count: int = 0
    rubric_title: str = ""
    dimension_versions: list[dict] = field(default_factory=list)


@dataclass
class GeneratedScoreSuggestions:
    dimension_suggestions: list[dict]  # [{dimension_version_id, suggested_rating, suggested_comment, confidence}]
    overall_notes: str = ""
    provider: str = "mock"
    model: str = "mock"


# ── Mock provider ───────────────────────────────────────────────────────────


async def mock_generate_score_suggestions(params: ScoreSuggestionParams) -> GeneratedScoreSuggestions:
    """Deterministic mock — returns rating=4, simple comment for each dimension."""
    suggestions = []
    for d in params.dimension_versions:
        suggestions.append({
            "dimension_version_id": d["id"],
            "suggested_rating": 4,
            "suggested_comment": f"Mock: The response demonstrates adequate {d['name'].lower()}.",
            "confidence": 0.75,
        })
    return GeneratedScoreSuggestions(
        dimension_suggestions=suggestions,
        overall_notes="Mock AI: this is a deterministic suggestion for testing.",
        provider="mock",
        model="mock",
    )


# ── Real provider (OpenAI) ──────────────────────────────────────────────────


async def openai_generate_score_suggestions(params: ScoreSuggestionParams) -> GeneratedScoreSuggestions:
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise ValueError("OPENAI_API_KEY not configured")

    dim_block = ""
    for d in params.dimension_versions:
        desc = (d.get("description") or "").strip()
        dim_block += f"- {d['name']} (id={d['id']}): {desc}\n"

    system_prompt = (
        "You are an experienced NSW Selective School writing assessor providing "
        "draft rubric dimension ratings for a teacher to review. "
        "For each dimension, suggest a rating (1-5) and a brief comment explaining "
        "the rationale. Also include a confidence score (0.0-1.0). "
        "Your suggestions are drafts only — the human reviewer makes the final decision. "
        "Return ONLY valid JSON with this exact structure:\n"
        '{"dimension_suggestions": [{"dimension_version_id": "...", "suggested_rating": 3, '
        '"suggested_comment": "...", "confidence": 0.8}], '
        '"overall_notes": "..."}'
    )

    user_prompt = (
        f"TASK: {params.task_title}\n"
        f"PROMPT: {params.task_prompt}\n"
        f"INSTRUCTIONS: {params.task_instructions or 'None'}\n"
        f"RUBRIC: {params.rubric_title}\n"
        f"DIMENSIONS:\n{dim_block}\n"
        f"STUDENT RESPONSE ({params.word_count} words):\n{params.submission_content}\n\n"
        "Provide suggested ratings and comments for each dimension."
    )

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
                "response_format": {"type": "json_object"},
            },
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)

    dims = parsed.get("dimension_suggestions", [])
    return GeneratedScoreSuggestions(
        dimension_suggestions=dims if isinstance(dims, list) else [dims],
        overall_notes=parsed.get("overall_notes", ""),
        provider="openai",
        model="gpt-4o-mini",
    )


# ── Provider registry ──────────────────────────────────────────────────────

_PROVIDERS = {
    "mock": mock_generate_score_suggestions,
    "openai": openai_generate_score_suggestions,
}


async def generate_score_suggestions(params: ScoreSuggestionParams, provider_name: str = "mock") -> GeneratedScoreSuggestions:
    provider = _PROVIDERS.get(provider_name)
    if not provider:
        raise ValueError(f"Unknown score suggestion provider: {provider_name}")
    return await provider(params)
