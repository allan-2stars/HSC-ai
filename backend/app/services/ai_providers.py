"""AI question generation providers.

Each provider implements:
    async def generate(params: GenerationParams) -> tuple[list[GeneratedQuestion], dict | None]

Returns (questions, token_usage). token_usage is None for mock, dict for real providers.

Real providers use structured JSON output. No free-form text parsing.
"""
import json
import os
import random
from dataclasses import dataclass, field

import httpx

from app.core.config import settings


@dataclass
class GenerationParams:
    outcome_code: str = ""
    outcome_title: str = ""
    subject_name: str = ""
    exam_type_name: str = ""
    framework_name: str = ""
    count: int = 5
    difficulty_mix: dict = field(default_factory=lambda: {"easy": 33, "medium": 34, "hard": 33})


@dataclass
class GeneratedQuestion:
    question_text: str
    options: list[dict]
    correct_answer: str
    explanation: str
    difficulty: str
    curriculum_outcome_code: str
    provider: str = "mock"


# ── System Prompt ────────────────────────────────────────────────────────────

_BUILD_SYSTEM_PROMPT = lambda p: (
    f"You are generating NSW exam preparation questions for the following curriculum outcome:\n"
    f"Outcome: {p.outcome_code} — {p.outcome_title}\n"
    f"Subject: {p.subject_name}\n"
    f"Exam Type: {p.exam_type_name}\n"
    f"Framework: {p.framework_name}\n\n"
    f"Generate {p.count} multiple-choice questions targeting this outcome.\n"
    f"Difficulty distribution requested: {json.dumps(p.difficulty_mix)}\n\n"
    f"Return ONLY a JSON object with this exact structure:\n"
    f'{{"questions": [{{"question_text": "...", "options": [{{"label": "A", "text": "...", "is_correct": false}}, ...], "correct_answer": "B", "explanation": "...", "difficulty": "medium"}}]}}\n\n'
    f"Rules:\n"
    f"- Exactly 4 options per question (A, B, C, D)\n"
    f"- Exactly 1 correct answer per question\n"
    f"- Explanation must be detailed and educational (≥50 characters)\n"
    f"- Questions must be appropriate for Year 5-6 NSW students\n"
    f"- Difficulties: easy, medium, hard\n"
    f"- Return valid JSON only. No markdown, no extra text."
)


# ── JSON Parsing ─────────────────────────────────────────────────────────────

def _parse_structured_response(text: str) -> list[dict]:
    """Parse LLM response into list of question dicts. Rejects malformed responses."""
    text = text.strip()
    # Strip markdown code fences if present
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

    if not isinstance(data, dict) or "questions" not in data:
        raise ValueError("Response missing 'questions' key")

    questions = data["questions"]
    if not isinstance(questions, list) or len(questions) == 0:
        raise ValueError("'questions' is not a non-empty array")

    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            raise ValueError(f"Question {i} is not an object")
        if not q.get("question_text"):
            raise ValueError(f"Question {i} missing question_text")
        if not isinstance(q.get("options"), list) or len(q["options"]) < 2:
            raise ValueError(f"Question {i} has insufficient options")

    return questions


# ── Cost Estimation ──────────────────────────────────────────────────────────

_COST_PER_1K = {
    "openai": {"prompt": 0.0025, "completion": 0.010},
    "claude": {"prompt": 0.003, "completion": 0.015},
    "deepseek": {"prompt": 0.00014, "completion": 0.00028},
    "ollama": {"prompt": 0.0, "completion": 0.0},
}


def _estimate_cost(provider: str, token_usage: dict) -> float:
    rates = _COST_PER_1K.get(provider, {"prompt": 0.0, "completion": 0.0})
    prompt_cost = (token_usage.get("prompt_tokens", 0) / 1000) * rates["prompt"]
    completion_cost = (token_usage.get("completion_tokens", 0) / 1000) * rates["completion"]
    return round(prompt_cost + completion_cost, 6)


# ── OpenAI Provider ──────────────────────────────────────────────────────────

async def openai_generate(params: GenerationParams) -> tuple[list[GeneratedQuestion], dict | None]:
    """Generate questions using OpenAI's chat completions API."""
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise ValueError("OPENAI_API_KEY not configured")

    system_prompt = _BUILD_SYSTEM_PROMPT(params)

    async with httpx.AsyncClient(timeout=120) as client:
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
                    {"role": "user", "content": f"Generate {params.count} questions now."},
                ],
                "temperature": 0.7,
                "max_tokens": 4000,
            },
        )
        resp.raise_for_status()
        body = resp.json()

    content = body["choices"][0]["message"]["content"]
    token_usage = {
        "prompt_tokens": body.get("usage", {}).get("prompt_tokens", 0),
        "completion_tokens": body.get("usage", {}).get("completion_tokens", 0),
        "total_tokens": body.get("usage", {}).get("total_tokens", 0),
    }

    questions_data = _parse_structured_response(content)
    return [
        GeneratedQuestion(
            question_text=q["question_text"],
            options=q["options"],
            correct_answer=q["correct_answer"],
            explanation=q["explanation"],
            difficulty=q.get("difficulty", "medium"),
            curriculum_outcome_code=params.outcome_code,
            provider="openai",
        )
        for q in questions_data
    ], token_usage


# ── Claude Provider ──────────────────────────────────────────────────────────

async def claude_generate(params: GenerationParams) -> tuple[list[GeneratedQuestion], dict | None]:
    """Generate questions using Anthropic's Claude API."""
    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not configured")

    system_prompt = _BUILD_SYSTEM_PROMPT(params)

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 4000,
                "system": system_prompt,
                "messages": [
                    {"role": "user", "content": f"Generate {params.count} questions now. Return JSON only."},
                ],
            },
        )
        resp.raise_for_status()
        body = resp.json()

    content = body["content"][0]["text"]
    token_usage = {
        "prompt_tokens": body.get("usage", {}).get("input_tokens", 0),
        "completion_tokens": body.get("usage", {}).get("output_tokens", 0),
        "total_tokens": (body.get("usage", {}).get("input_tokens", 0)
                         + body.get("usage", {}).get("output_tokens", 0)),
    }

    questions_data = _parse_structured_response(content)
    return [
        GeneratedQuestion(
            question_text=q["question_text"],
            options=q["options"],
            correct_answer=q["correct_answer"],
            explanation=q["explanation"],
            difficulty=q.get("difficulty", "medium"),
            curriculum_outcome_code=params.outcome_code,
            provider="claude",
        )
        for q in questions_data
    ], token_usage


# ── DeepSeek Provider ────────────────────────────────────────────────────────

async def deepseek_generate(params: GenerationParams) -> tuple[list[GeneratedQuestion], dict | None]:
    """Generate questions using DeepSeek's API (OpenAI-compatible)."""
    api_key = settings.DEEPSEEK_API_KEY
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY not configured")

    system_prompt = _BUILD_SYSTEM_PROMPT(params)

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Generate {params.count} questions now."},
                ],
                "temperature": 0.7,
                "max_tokens": 4000,
            },
        )
        resp.raise_for_status()
        body = resp.json()

    content = body["choices"][0]["message"]["content"]
    token_usage = {
        "prompt_tokens": body.get("usage", {}).get("prompt_tokens", 0),
        "completion_tokens": body.get("usage", {}).get("completion_tokens", 0),
        "total_tokens": body.get("usage", {}).get("total_tokens", 0),
    }

    questions_data = _parse_structured_response(content)
    return [
        GeneratedQuestion(
            question_text=q["question_text"],
            options=q["options"],
            correct_answer=q["correct_answer"],
            explanation=q["explanation"],
            difficulty=q.get("difficulty", "medium"),
            curriculum_outcome_code=params.outcome_code,
            provider="deepseek",
        )
        for q in questions_data
    ], token_usage


# ── Ollama Provider ──────────────────────────────────────────────────────────

async def ollama_generate(params: GenerationParams) -> tuple[list[GeneratedQuestion], dict | None]:
    """Generate questions using Ollama (local)."""
    base_url = settings.OLLAMA_BASE_URL.rstrip("/")

    system_prompt = _BUILD_SYSTEM_PROMPT(params)

    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            f"{base_url}/api/chat",
            json={
                "model": "llama3",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Generate {params.count} questions now. Return JSON only."},
                ],
                "stream": False,
            },
        )
        resp.raise_for_status()
        body = resp.json()

    content = body["message"]["content"]
    eval_count = body.get("eval_count", 0)
    token_usage = {
        "prompt_tokens": body.get("prompt_eval_count", 0),
        "completion_tokens": eval_count,
        "total_tokens": body.get("prompt_eval_count", 0) + eval_count,
    }

    questions_data = _parse_structured_response(content)
    return [
        GeneratedQuestion(
            question_text=q["question_text"],
            options=q["options"],
            correct_answer=q["correct_answer"],
            explanation=q["explanation"],
            difficulty=q.get("difficulty", "medium"),
            curriculum_outcome_code=params.outcome_code,
            provider="ollama",
        )
        for q in questions_data
    ], token_usage


# ── Mock Provider ────────────────────────────────────────────────────────────

_MOCK_TEMPLATES = [
    {
        "question_text": "If a student has 24 apples and wants to divide them equally among 6 friends, how many apples does each friend get?",
        "options": [
            {"label": "A", "text": "3", "is_correct": False},
            {"label": "B", "text": "4", "is_correct": True},
            {"label": "C", "text": "6", "is_correct": False},
            {"label": "D", "text": "8", "is_correct": False},
        ],
        "correct_answer": "B",
        "explanation": "24 ÷ 6 = 4. Each friend gets 4 apples.",
        "difficulty": "easy",
    },
    {
        "question_text": "What is the value of 3/4 + 1/2?",
        "options": [
            {"label": "A", "text": "4/6", "is_correct": False},
            {"label": "B", "text": "5/4", "is_correct": True},
            {"label": "C", "text": "1", "is_correct": False},
            {"label": "D", "text": "3/8", "is_correct": False},
        ],
        "correct_answer": "B",
        "explanation": "Convert 1/2 to 2/4. Then 3/4 + 2/4 = 5/4 = 1¼.",
        "difficulty": "medium",
    },
    {
        "question_text": "A number pattern starts at 3 and each term is multiplied by 2 to get the next term. What is the 5th term?",
        "options": [
            {"label": "A", "text": "24", "is_correct": False},
            {"label": "B", "text": "48", "is_correct": True},
            {"label": "C", "text": "96", "is_correct": False},
            {"label": "D", "text": "12", "is_correct": False},
        ],
        "correct_answer": "B",
        "explanation": "Sequence: 3, 6, 12, 24, 48. The 5th term is 48.",
        "difficulty": "medium",
    },
    {
        "question_text": "A train travels 180 km in 3 hours. What is its average speed in km/h?",
        "options": [
            {"label": "A", "text": "30 km/h", "is_correct": False},
            {"label": "B", "text": "45 km/h", "is_correct": False},
            {"label": "C", "text": "60 km/h", "is_correct": True},
            {"label": "D", "text": "90 km/h", "is_correct": False},
        ],
        "correct_answer": "C",
        "explanation": "Speed = Distance ÷ Time = 180 km ÷ 3 h = 60 km/h.",
        "difficulty": "easy",
    },
    {
        "question_text": "A rectangular garden has a length of 12 m and a width of 8 m. A path 1 m wide runs around the entire garden on the inside. What is the area of the garden excluding the path?",
        "options": [
            {"label": "A", "text": "60 m²", "is_correct": True},
            {"label": "B", "text": "80 m²", "is_correct": False},
            {"label": "C", "text": "96 m²", "is_correct": False},
            {"label": "D", "text": "70 m²", "is_correct": False},
        ],
        "correct_answer": "A",
        "explanation": "Inner dimensions: (12-2)=10m by (8-2)=6m. Area = 10×6 = 60 m².",
        "difficulty": "hard",
    },
    {
        "question_text": "If the ratio of boys to girls in a class is 3:2 and there are 25 students in total, how many boys are there?",
        "options": [
            {"label": "A", "text": "10", "is_correct": False},
            {"label": "B", "text": "12", "is_correct": False},
            {"label": "C", "text": "15", "is_correct": True},
            {"label": "D", "text": "18", "is_correct": False},
        ],
        "correct_answer": "C",
        "explanation": "Ratio 3:2 means 5 parts total. Each part = 25÷5 = 5. Boys = 3×5 = 15.",
        "difficulty": "medium",
    },
    {
        "question_text": "What is 0.25 expressed as a fraction in simplest form?",
        "options": [
            {"label": "A", "text": "2/5", "is_correct": False},
            {"label": "B", "text": "1/4", "is_correct": True},
            {"label": "C", "text": "25/100", "is_correct": False},
            {"label": "D", "text": "2/8", "is_correct": False},
        ],
        "correct_answer": "B",
        "explanation": "0.25 = 25/100 = 1/4 in simplest form.",
        "difficulty": "easy",
    },
    {
        "question_text": "The mean of five numbers is 12. Four of the numbers are 8, 14, 10, and 16. What is the fifth number?",
        "options": [
            {"label": "A", "text": "10", "is_correct": False},
            {"label": "B", "text": "12", "is_correct": True},
            {"label": "C", "text": "14", "is_correct": False},
            {"label": "D", "text": "16", "is_correct": False},
        ],
        "correct_answer": "B",
        "explanation": "Sum = 12×5 = 60. Sum of known = 8+14+10+16 = 48. Fifth = 60-48 = 12.",
        "difficulty": "medium",
    },
    {
        "question_text": "A shop offers a 20% discount on an item priced at $80. How much does the item cost after the discount?",
        "options": [
            {"label": "A", "text": "$60", "is_correct": False},
            {"label": "B", "text": "$64", "is_correct": True},
            {"label": "C", "text": "$68", "is_correct": False},
            {"label": "D", "text": "$72", "is_correct": False},
        ],
        "correct_answer": "B",
        "explanation": "Discount = 20% of $80 = $16. Final price = $80 - $16 = $64.",
        "difficulty": "easy",
    },
    {
        "question_text": "A cube has a volume of 64 cm³. What is its surface area?",
        "options": [
            {"label": "A", "text": "64 cm²", "is_correct": False},
            {"label": "B", "text": "96 cm²", "is_correct": True},
            {"label": "C", "text": "128 cm²", "is_correct": False},
            {"label": "D", "text": "384 cm²", "is_correct": False},
        ],
        "correct_answer": "B",
        "explanation": "Side length = ³√64 = 4 cm. Surface area = 6 × 4² = 6 × 16 = 96 cm².",
        "difficulty": "hard",
    },
    {
        "question_text": "What is the probability of rolling an even number on a standard six-sided die?",
        "options": [
            {"label": "A", "text": "1/6", "is_correct": False},
            {"label": "B", "text": "1/3", "is_correct": False},
            {"label": "C", "text": "1/2", "is_correct": True},
            {"label": "D", "text": "2/3", "is_correct": False},
        ],
        "correct_answer": "C",
        "explanation": "Even numbers on a die: 2, 4, 6. Probability = 3/6 = 1/2.",
        "difficulty": "easy",
    },
    {
        "question_text": "A water tank is 2/5 full. After adding 30 litres, it becomes 3/5 full. What is the total capacity of the tank?",
        "options": [
            {"label": "A", "text": "100 litres", "is_correct": False},
            {"label": "B", "text": "120 litres", "is_correct": False},
            {"label": "C", "text": "150 litres", "is_correct": True},
            {"label": "D", "text": "200 litres", "is_correct": False},
        ],
        "correct_answer": "C",
        "explanation": "30 litres = 1/5 of capacity. Total = 30 × 5 = 150 litres.",
        "difficulty": "medium",
    },
]


async def mock_generate(params: GenerationParams) -> tuple[list[GeneratedQuestion], None]:
    """Generate questions from a curated template pool."""
    pool = random.sample(_MOCK_TEMPLATES, min(len(_MOCK_TEMPLATES), params.count))
    results = []
    difficulties = []
    for diff, pct in params.difficulty_mix.items():
        n = max(1, round(params.count * pct / 100))
        difficulties.extend([diff] * n)
    random.shuffle(difficulties)

    for i, tmpl in enumerate(pool):
        diff = difficulties[i % len(difficulties)] if difficulties else "medium"
        results.append(GeneratedQuestion(
            question_text=tmpl["question_text"],
            options=tmpl["options"],
            correct_answer=tmpl["correct_answer"],
            explanation=tmpl["explanation"],
            difficulty=diff,
            curriculum_outcome_code=params.outcome_code,
            provider="mock",
        ))

    while len(results) < params.count:
        tmpl = random.choice(_MOCK_TEMPLATES)
        diff = difficulties[len(results) % len(difficulties)] if difficulties else "medium"
        results.append(GeneratedQuestion(
            question_text=tmpl["question_text"] + f" (variant {len(results) + 1})",
            options=tmpl["options"],
            correct_answer=tmpl["correct_answer"],
            explanation=tmpl["explanation"],
            difficulty=diff,
            curriculum_outcome_code=params.outcome_code,
            provider="mock",
        ))

    return results[:max(1, params.count)], None


# ── Provider Registry ────────────────────────────────────────────────────────

_PROVIDERS = {
    "mock": mock_generate,
    "openai": openai_generate,
    "claude": claude_generate,
    "deepseek": deepseek_generate,
    "ollama": ollama_generate,
}


def get_provider(name: str):
    """Get a provider function by name. Returns mock if provider not found."""
    return _PROVIDERS.get(name, mock_generate)
