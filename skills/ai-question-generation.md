# Skill: AI Question Generation

Use this skill when implementing AI-generated draft question features.

## Rules

- AI-generated content is draft only.
- Admin review is mandatory. No exceptions.
- No AI-generated question can be published automatically.
- Every generated question must include a correct answer and full explanation.
- Minimize personal data sent to AI providers.
- Generated questions enter the review queue with `source_type: ai` and `content_ownership: original`.
- The admin may edit any field during review before approving.

## Provider Strategy

Use the AI provider abstraction. Do not call provider APIs directly from business routes.

Use the appropriate domain skill for the target exam type:

- OC questions → `nsw-oc-question-generation` skill
- Selective questions → `nsw-selective-question-generation` skill

## Output Requirements

Every AI-generated question must include:

- `stem` — the question text
- `options` — answer options (for MCQ, minimum 4)
- `correct_answer` — clearly identified
- `explanation` — full explanation of why the answer is correct
- `subject` — e.g., Mathematics, English
- `exam_type` — OC or Selective
- `year_level` — 4, 5, or 6
- `topic` — specific topic label
- `difficulty` — easy, medium, or hard (AI estimate; admin may revise)

Incomplete output (missing any required field) must not be inserted into the review queue. Return an error or regenerate.

## Privacy

Do not include in the AI prompt or payload:

- Student names
- Student identifiers
- Parent information
- Billing or subscription data
- Any personally identifying information
