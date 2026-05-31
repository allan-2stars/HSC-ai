# AI Provider Strategy

## 1. Purpose

The system must support AI-assisted features without coupling business logic to a single model provider.

The AI layer should be provider-independent and switchable.

## 2. Supported Provider Targets

Potential providers:

- DeepSeek
- OpenAI
- Claude
- Gemini
- Ollama
- OpenRouter
- CC Switch

Development default may be DeepSeek because it is cheaper and already available.

Production default must remain configurable.

## 3. AI Use Cases

V1/admin:

- OCR structure extraction
- AI-generated draft questions
- Explanation drafting
- Topic/difficulty tagging assistance

Premium student/parent features:

- Weakness analysis
- Practice recommendation
- AI tutor explanation
- Readiness summary

## 4. Provider Abstraction

Business services should call an internal interface such as:

- generate_question_draft
- generate_explanation
- extract_questions_from_ocr
- analyze_weakness
- recommend_practice

The provider router decides which backend model to use.

## 5. Data Safety

Do not send unnecessary child personal data to AI providers.

For most AI features, use anonymized or minimized input:

- topic
- question ID
- answer correctness
- generic performance pattern

Avoid sending:

- child full name
- parent identity
- email
- payment data
- unnecessary personal information

## 6. DeepSeek Commercial Caution

DeepSeek can be useful for development/testing. For Australian commercial launch involving children, treat provider selection as a legal/privacy risk area.

Production should support switching to providers with stronger enterprise/privacy posture if required.

## 7. Logging

AI usage should log:

- provider
- feature
- user/admin scope
- token estimate
- error status
- cost estimate

Do not log raw sensitive prompts unless explicitly required and protected.

## 8. Premium Gating

AI features are Premium-only except limited trial usage.

Examples:

- Limited free AI explanations per month
- Limited recommendations per week

## 9. Non-Goals for MVP

- Fully autonomous AI tutoring without guardrails.
- AI-generated content auto-publishing.
- AI long-answer marking for HSC.
