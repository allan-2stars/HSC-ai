"""AI writing-feedback draft providers (M5.3).

Each provider implements:
    async def generate(params: FeedbackParams) -> GeneratedFeedbackDraft

Providers generate **draft** feedback only. They never assign rubric scores, never
publish, and never receive student PII — ``FeedbackParams`` carries only the task
definition, the submission text, and (optionally) the rubric dimension labels.

Real providers use structured JSON output; no free-form text parsing. The default
provider is ``mock`` so the feature works deterministically and offline.
"""
import json
from dataclasses import dataclass, field

import httpx

from app.core.config import settings

# Bump when the prompt or output contract changes, so drafts are traceable.
PROMPT_VERSION = "wfd-v1"


@dataclass
class FeedbackParams:
    task_title: str = ""
    task_prompt: str = ""
    task_instructions: str = ""
    submission_content: str = ""
    word_count: int = 0
    # [{"name": str, "description": str | None}] — empty when no rubric is assigned.
    rubric_dimensions: list[dict] = field(default_factory=list)


@dataclass
class GeneratedFeedbackDraft:
    strengths: list[str]
    improvements: list[str]
    next_steps: list[str]
    overall_feedback: str
    provider: str = "mock"
    model: str = "mock"


# ── System prompt ─────────────────────────────────────────────────────────────


def _build_system_prompt(p: FeedbackParams) -> str:
    rubric_text = ""
    if p.rubric_dimensions:
        lines = "\n".join(
            f"- {d['name']}: {(d.get('description') or '').strip()}" for d in p.rubric_dimensions
        )
        rubric_text = (
            "\nThe response is assessed against these rubric dimensions "
            f"(do NOT assign scores or marks):\n{lines}\n"
        )
    return (
        "You are an experienced NSW Selective School writing tutor drafting feedback for a "
        "teacher to review. You provide qualitative guidance only. You must NOT assign marks, "
        "scores, grades, or rubric ratings.\n\n"
        f"Task: {p.task_title}\n"
        f"Prompt: {p.task_prompt}\n"
        f"Instructions: {p.task_instructions or '(none)'}\n"
        f"{rubric_text}\n"
        f"Student response ({p.word_count} words):\n\"\"\"\n{p.submission_content}\n\"\"\"\n\n"
        "Return ONLY a JSON object with this exact structure:\n"
        '{"strengths": ["..."], "improvements": ["..."], "next_steps": ["..."], '
        '"overall_feedback": "..."}\n\n'
        "Rules:\n"
        "- Each list holds short, specific, student-friendly points.\n"
        "- overall_feedback is a brief encouraging paragraph.\n"
        "- No marks, scores, or grades anywhere.\n"
        "- Return valid JSON only. No markdown, no extra text."
    )


# ── JSON parsing ──────────────────────────────────────────────────────────────


def _parse_feedback_response(text: str) -> dict:
    """Parse an LLM response into the structured feedback dict. Rejects malformed input."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise ValueError("Response is not valid JSON")

    if not isinstance(data, dict):
        raise ValueError("Response is not a JSON object")
    if "overall_feedback" not in data:
        raise ValueError("Response missing 'overall_feedback'")

    def _as_list(value) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("Expected a list of feedback points")
        return [str(v).strip() for v in value if str(v).strip()]

    return {
        "strengths": _as_list(data.get("strengths")),
        "improvements": _as_list(data.get("improvements")),
        "next_steps": _as_list(data.get("next_steps")),
        "overall_feedback": str(data.get("overall_feedback") or "").strip(),
    }


def _draft_from_parsed(parsed: dict, provider: str, model: str) -> GeneratedFeedbackDraft:
    return GeneratedFeedbackDraft(
        strengths=parsed["strengths"],
        improvements=parsed["improvements"],
        next_steps=parsed["next_steps"],
        overall_feedback=parsed["overall_feedback"],
        provider=provider,
        model=model,
    )


# ── OpenAI provider ───────────────────────────────────────────────────────────


async def openai_feedback(params: FeedbackParams) -> GeneratedFeedbackDraft:
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise ValueError("OPENAI_API_KEY not configured")
    model = "gpt-4o-mini"
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": _build_system_prompt(params)},
                    {"role": "user", "content": "Draft the feedback now. Return JSON only."},
                ],
                "temperature": 0.5,
                "max_tokens": 1500,
            },
        )
        resp.raise_for_status()
        body = resp.json()
    content = body["choices"][0]["message"]["content"]
    return _draft_from_parsed(_parse_feedback_response(content), "openai", model)


# ── Claude provider ───────────────────────────────────────────────────────────


async def claude_feedback(params: FeedbackParams) -> GeneratedFeedbackDraft:
    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not configured")
    model = "claude-sonnet-4-20250514"
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 1500,
                "system": _build_system_prompt(params),
                "messages": [
                    {"role": "user", "content": "Draft the feedback now. Return JSON only."},
                ],
            },
        )
        resp.raise_for_status()
        body = resp.json()
    content = body["content"][0]["text"]
    return _draft_from_parsed(_parse_feedback_response(content), "claude", model)


# ── Ollama provider (local) ───────────────────────────────────────────────────


async def ollama_feedback(params: FeedbackParams) -> GeneratedFeedbackDraft:
    base_url = settings.OLLAMA_BASE_URL.rstrip("/")
    model = "llama3"
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            f"{base_url}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": _build_system_prompt(params)},
                    {"role": "user", "content": "Draft the feedback now. Return JSON only."},
                ],
                "stream": False,
            },
        )
        resp.raise_for_status()
        body = resp.json()
    content = body["message"]["content"]
    return _draft_from_parsed(_parse_feedback_response(content), "ollama", model)


# ── Mock provider (default) ───────────────────────────────────────────────────


async def mock_feedback(params: FeedbackParams) -> GeneratedFeedbackDraft:
    """Deterministic placeholder draft. References only the task/submission shape,
    never any personal information. Default provider for development and tests."""
    dimension_note = ""
    if params.rubric_dimensions:
        names = ", ".join(d["name"] for d in params.rubric_dimensions)
        dimension_note = f" Consider the rubric focus areas ({names}) when revising."
    return GeneratedFeedbackDraft(
        strengths=[
            "The response stays on the task and addresses the prompt.",
            "Ideas are sequenced in an order the reader can follow.",
        ],
        improvements=[
            "Vary sentence openings and lengths to improve flow.",
            "Add specific, sensory detail to strengthen description.",
        ],
        next_steps=[
            "Revise one paragraph to replace a general statement with a concrete example.",
            "Proofread for punctuation in longer, complex sentences.",
        ],
        overall_feedback=(
            f"This {params.word_count}-word response makes a solid attempt at the task. "
            f"Focus next on richer description and sentence variety.{dimension_note} "
            "(Draft feedback for reviewer editing — not shown to the student.)"
        ),
        provider="mock",
        model="mock",
    )


# ── Provider registry ─────────────────────────────────────────────────────────

_PROVIDERS = {
    "mock": mock_feedback,
    "openai": openai_feedback,
    "claude": claude_feedback,
    "ollama": ollama_feedback,
}


def get_feedback_provider(name: str | None):
    """Resolve a feedback provider by name, defaulting to the mock provider."""
    return _PROVIDERS.get(name or "mock", mock_feedback)
