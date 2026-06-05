# AI Question Generation

## 1. Purpose

The AI Question Generation feature allows administrators to generate draft questions targeting specific curriculum outcome gaps. Generated questions enter the standard review pipeline (draft → review → approved → published) — **no AI-generated question can bypass review**.

## 2. Workflow

```
Admin selects curriculum outcome (with gap)
        │
        ▼
Configure generation:
  - number of questions
  - difficulty distribution
  - provider (mock/OpenAI/Claude/DeepSeek/Ollama)
        │
        ▼
Preview — provider returns structured questions
        │
        ▼
Admin reviews generated questions
  - valid questions shown with options/answers/explanations
  - invalid questions flagged with errors
        │
        ▼
Execute — save valid questions as DRAFT
  - source_type = ai
  - content_ownership = original
  - auto-mapped to the selected outcome
        │
        ▼
Questions appear in Review Queue
  - /admin/content/review?source_type=ai
        │
        ▼
Standard review → approve → publish workflow
```

## 3. Provider Architecture

```
┌─────────────────────────────────┐
│      AI Generation Service      │
│  (ai_service.py)                │
│                                 │
│  preview_generation()           │
│  execute_generation()           │
│  _validate_generated_question() │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────┐
│      Provider Registry      │
│  (ai_providers.py)          │
│                             │
│  get_provider("mock")        │
│  get_provider("openai")     │
│  get_provider("claude")     │
│  ...                        │
└────────────┬────────────────┘
             │
     ┌───────┴───────┐
     ▼               ▼
┌─────────┐   ┌──────────────┐
│  Mock   │   │  Real        │
│Provider │   │  Providers   │
│ (always │   │  (optional,  │
│  avail) │   │   env-gated) │
└─────────┘   └──────────────┘
```

### Provider Interface

Each provider implements:

```python
async def generate(params: GenerationParams) -> list[GeneratedQuestion]
```

Where `GenerationParams` contains:
- `outcome_code`, `outcome_title` — curriculum target
- `count` — number of questions to generate
- `difficulty_mix` — dict of easy/medium/hard percentages
- `subject_name`, `exam_type_name` — context

## 4. Mock Provider

The mock provider (`ai_providers.py`) returns questions from a curated pool of 12 high-quality Mathematics MCQ templates covering:
- Arithmetic, fractions, decimals, percentages
- Geometry, measurement, volume
- Probability, statistics, number patterns

Templates are shuffled and selected randomly. Difficulty tags are assigned based on the requested distribution. When more questions are requested than templates exist, variants are generated with numbered suffixes.

## 5. Real Provider Integration

Provider stubs for OpenAI, Claude, DeepSeek, and Ollama can be added by creating `async def openai_generate(params: GenerationParams)` functions with appropriate API calls and registering them in `_PROVIDERS`.

Environment variables control provider availability:
- `AI_PROVIDER` — default provider name
- `OPENAI_API_KEY` — OpenAI API key
- `ANTHROPIC_API_KEY` — Claude API key
- `OLLAMA_HOST` — Ollama endpoint

## 6. Validation Rules

Every generated question is validated before saving:

| Rule | Rejection |
|---|---|
| question_text < 10 characters | Yes |
| Less than 2 options | Yes |
| Not exactly 1 correct answer | Yes |
| correct_answer doesn't match any option label | Yes |
| Invalid difficulty value | Yes |
| explanation < 10 characters | Yes |

Invalid questions are reported in the preview but never saved.

## 7. APIs

| Method | Path | Purpose |
|---|---|---|
| POST | `/admin/content/ai-generate/preview` | Generate preview (no save) |
| POST | `/admin/content/ai-generate/execute` | Generate and save as draft |
| GET | `/admin/content/ai-generate/jobs` | List generation job history |
| GET | `/admin/content/ai-generate/jobs/{id}` | Job detail |

All endpoints require admin authentication.

## 8. Safety Rules

1. **No auto-publish** — all AI questions are `status = draft`, `source_type = ai`
2. **Validation gate** — structured validation rejects malformed questions
3. **Curriculum mapping required** — every generated question is auto-mapped to a curriculum outcome
4. **Audit trail** — `AIGenerationJob` records provider, outcome, counts, timestamps
5. **Mock-only by default** — real providers require explicit environment configuration

## 9. Limitations

1. **Mock provider template pool is small** (12 templates) — suitable for dev/testing, not production seeding at scale
2. **No image/LaTeX support** — generated content is text-only
3. **Single-outcome targeting** — each generation targets one outcome at a time
4. **No fine-tuning** — providers are not fine-tuned on NSW curriculum content
5. **Synchronous generation** — large requests may time out (max 50 questions recommended)
