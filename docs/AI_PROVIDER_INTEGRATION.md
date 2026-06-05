# AI Provider Integration

## 1. Supported Providers

| Provider | Status | Model | API Endpoint |
|---|---|---|---|
| OpenAI | ✅ Implemented | GPT-4o-mini | `api.openai.com/v1/chat/completions` |
| Claude (Anthropic) | ✅ Implemented | Sonnet 4 | `api.anthropic.com/v1/messages` |
| DeepSeek | ✅ Implemented | DeepSeek Chat | `api.deepseek.com/chat/completions` |
| Ollama | ✅ Implemented | Llama 3 | Local (configurable) |
| Mock | ✅ (default) | Template pool | N/A |

All real providers are optional and gated by environment variables. When no API key is configured, requests fail with a clear error message.

## 2. Configuration

### Environment Variables

| Variable | Provider | Required |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI | Yes (for OpenAI) |
| `ANTHROPIC_API_KEY` | Claude | Yes (for Claude) |
| `DEEPSEEK_API_KEY` | DeepSeek | Yes (for DeepSeek) |
| `OLLAMA_BASE_URL` | Ollama | No (default: `http://localhost:11434`) |

Add to `.env`:
```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
DEEPSEEK_API_KEY=sk-...
OLLAMA_BASE_URL=http://localhost:11434
```

None of these are required — the mock provider works without any API keys.

## 3. Cost Considerations

Estimated cost per 1000 tokens (USD):

| Provider | Prompt | Completion | 20 Questions (~8000 tokens) |
|---|---|---|---|
| OpenAI (GPT-4o-mini) | $0.0025 | $0.010 | ~$0.05 |
| Claude (Sonnet 4) | $0.003 | $0.015 | ~$0.07 |
| DeepSeek | $0.00014 | $0.00028 | <$0.01 |
| Ollama | $0.00 | $0.00 | $0.00 |

Token usage and estimated cost are stored on each `AIGenerationJob`.

## 4. Prompt Design

The system prompt is dynamically built for each request using the selected curriculum outcome:

```
You are generating NSW exam preparation questions for:
Outcome: OC-MATH-FRAC — Fractions
Subject: Mathematics
Exam Type: OC
Framework: OC Mathematics 2026

Generate N multiple-choice questions targeting this outcome.
Difficulty distribution: {"easy": 33, "medium": 34, "hard": 33}

Return ONLY a JSON object:
{"questions": [{"question_text": "...", "options": [{"label": "A", ...}], "correct_answer": "B", "explanation": "...", "difficulty": "medium"}]}

Rules:
- Exactly 4 options per question (A, B, C, D)
- Exactly 1 correct answer per question
- Explanation must be detailed and educational (≥50 characters)
- Questions appropriate for Year 5-6 NSW students
- Valid JSON only. No markdown, no extra text.
```

## 5. JSON Parsing

All provider responses are parsed through `_parse_structured_response()`:

1. **Strip markdown fences**: If the response is wrapped in ` ```json ... ``` `, the fences are removed
2. **JSON decode**: `json.loads()` — rejects malformed JSON
3. **Structure validation**: Must have a `questions` key with a non-empty array
4. **Per-question validation**: Each question must be a dict with `question_text` and non-empty `options`

Invalid responses are rejected with a specific error message. The admin sees the error in the preview UI.

## 6. Validation Flow

```
Provider response
  → _parse_structured_response()  (JSON parsing, structure check)
  → _validate_generated_question() (per-question: options count, correct answer, explanation length)
  → Valid questions shown in preview
  → Admin reviews
  → Execute button saves valid questions as draft (source_type=ai)
  → Invalid questions are discarded (counted as rejected)
```

## 7. Provider Interface

All providers follow the same interface:

```python
async def provider_name(params: GenerationParams) -> tuple[list[GeneratedQuestion], dict | None]:
    ...
    return questions, token_usage
```

- `params`: Contains `outcome_code`, `outcome_title`, `subject_name`, `exam_type_name`, `framework_name`, `count`, `difficulty_mix`
- Returns `(questions: list[GeneratedQuestion], token_usage: dict | None)`
- `token_usage` is `None` for mock, `{prompt_tokens, completion_tokens, total_tokens}` for real providers

New providers are registered in `_PROVIDERS` dict and become available in the UI dropdown automatically.

## 8. Cost Tracking

`AIGenerationJob` stores:
- `token_usage_json`: raw token counts from the provider
- `estimated_cost`: calculated from token usage × provider rates

Visible in the job detail API response and UI.

## 9. Error Handling

| Scenario | Status | Admin sees |
|---|---|---|
| No API key configured | 422 | "Provider error: OPENAI_API_KEY not configured" |
| API returns non-200 | 502 | "Provider API error: ..." |
| Response is not JSON | 422 | "Provider error: Response is not valid JSON" |
| Missing questions key | 422 | "Provider error: Response missing 'questions' key" |
| Empty questions | 422 | "Provider error: 'questions' is not a non-empty array" |
| Invalid question structure | — | Flagged as invalid in preview, not saved |

## 10. Safety

- All generated questions enter as `status = draft`, `source_type = ai`
- `content_ownership = internal_draft` — cannot be published without review
- Validation rejects malformed questions before saving
- Every generation creates an audit trail (`AIGenerationJob`)
- API keys are read from environment variables only — never stored in the database
