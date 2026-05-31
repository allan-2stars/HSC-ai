# Skill: AI Question Generation

Use this skill when implementing AI-generated draft question features.

## Rules

- AI-generated content is draft only.
- Admin review is mandatory.
- No AI-generated question can be published automatically.
- Every generated question must include a correct answer and full explanation.
- Minimize personal data sent to AI providers.

## Provider Strategy

Use the AI provider abstraction. Do not call provider APIs directly from business routes.
