# AI Provider Strategy

## 1. Purpose

The system must support AI-assisted features without coupling business logic to a single model provider.

The AI layer must be provider-independent and switchable via configuration. Provider selection is determined entirely by the `AI_PROVIDER` environment variable — no provider logic is hardcoded into business services.

---

## 2. Provider Classification

Providers are classified into two tiers: **Production Approved** and **Experimental**.

### Production Approved

These providers have been evaluated for use with Australian children's education data and may be used in production deployments with student-facing features (subject to data processing agreements being in place).

| Provider | Notes |
|---|---|
| **OpenAI** | Preferred production provider. API data is not used for training by default. Requires data processing agreement. Do not send student PII (name, DOB, contact details). |
| **Claude (Anthropic)** | Preferred production provider. No training on API data. Strong privacy posture. Requires data processing agreement. Do not send student PII. |

Production providers must be configured with:

- A signed data processing agreement (DPA) reviewed against Australian Privacy Principles
- Explicit opt-out from training data usage (API access typically provides this)
- A confirmed understanding that student writing responses (Category B payloads) are transmitted

### Experimental

These providers are available via the provider abstraction layer and may be used for development, testing, or admin-only features. They are not approved for production deployments where student data is involved.

| Provider | Approved Use | Restrictions |
|---|---|---|
| **Ollama** | Development, offline, admin question generation | No student data restriction — data stays local. Safe for all use cases. Best choice for privacy-sensitive contexts. |
| **DeepSeek** | Development and admin-only question generation | Must not receive student data. Subject to PRC data localisation law (see Section 3). Requires explicit opt-in via config. |
| **Gemini (Google)** | Admin question generation only | Review Google DPA before use. Do not use for student-facing features without confirmed DPA. |
| **OpenRouter** | Admin question generation only | Routing aggregator — document which underlying provider is receiving requests. Do not use for student data. |

Experimental providers are enabled via the `AI_PROVIDER_EXPERIMENTAL=true` environment variable. This flag must be absent or false in any production deployment handling student data.

---

## 3. DeepSeek — Experimental Status and Restrictions

DeepSeek is classified as **Experimental** and carries specific restrictions that must be understood before enabling it.

**Legal context:**

DeepSeek is subject to data localisation requirements under the People's Republic of China's Data Security Law and Cybersecurity Law. These laws require that data processed by PRC-based services may be subject to government access requests. This is incompatible with the platform's obligations under APP 8 of the Australian Privacy Act 1988, which requires that overseas disclosure of personal information meets equivalent privacy standards.

**What this means in practice:**

| Use Case | DeepSeek Permitted |
|---|---|
| Admin generating OC maths questions (no student data) | Yes, with `AI_PROVIDER_EXPERIMENTAL=true` |
| Admin OCR structure extraction (no student data) | Yes, with `AI_PROVIDER_EXPERIMENTAL=true` |
| Writing assessment (student response text) | No |
| Weakness analysis (student performance data) | No |
| Any payload containing student name, DOB, or contact details | No |

**Configuration:**

DeepSeek is enabled only when both conditions are met:

1. `AI_PROVIDER=deepseek` is set explicitly
2. `AI_PROVIDER_EXPERIMENTAL=true` is set

If `AI_PROVIDER_EXPERIMENTAL` is not `true`, the provider factory must refuse to initialise a DeepSeek provider and log a warning.

DeepSeek must never be the default provider in any environment.

---

## 4. Provider Abstraction

The provider abstraction ensures all AI calls go through a common interface. No business route handler or service imports a provider SDK directly.

### Environment Variable Configuration

```
AI_PROVIDER=openai              # Active provider for Category A (admin) features
AI_PROVIDER_STUDENT=openai      # Active provider for Category B (student-facing) features
                                # If unset, falls back to AI_PROVIDER
AI_PROVIDER_EXPERIMENTAL=false  # Must be true to enable experimental providers
```

### Provider Factory (conceptual)

```python
def get_provider(category: str = "admin") -> AIProvider:
    provider_name = settings.AI_PROVIDER_STUDENT if category == "student" else settings.AI_PROVIDER
    if provider_name in EXPERIMENTAL_PROVIDERS:
        if not settings.AI_PROVIDER_EXPERIMENTAL:
            raise ConfigurationError(
                f"Provider '{provider_name}' is experimental. "
                "Set AI_PROVIDER_EXPERIMENTAL=true to enable."
            )
    return PROVIDER_REGISTRY[provider_name]()
```

---

## 5. AI Use Cases

### Category A: Admin-Only Features

No student personal data involved. Admin provides subject, topic, difficulty parameters.

| Feature | Skill | Notes |
|---|---|---|
| OC question generation | `nsw-oc-question-generation` | Admin-only |
| Selective question generation | `nsw-selective-question-generation` | Admin-only |
| OCR structure extraction | — | Admin-only |
| Explanation drafting | — | Admin-only |
| Topic/difficulty tagging assistance | — | Admin-only |
| Question quality review | `question-quality-review` | Admin-only |

Category A features may use any approved or experimental provider.

### Category B: Student-Facing Features

May include student response content. No PII permitted.

| Feature | Skill | Notes |
|---|---|---|
| Writing assessment | `writing-assessment` | Contains student writing response |
| Weakness analysis | — | Contains anonymised performance data |
| Practice recommendations | — | Contains anonymised performance pattern |
| AI tutor explanation | — | Contains question + student answer |

Category B features must only use Production Approved providers. Student PII (name, DOB, contact details) must be stripped before the payload is constructed.

---

## 6. AI Skill System

The platform uses a structured skill system to define AI responsibilities. Skills are documented in the `skills/` directory and must be used by business services. Direct provider calls from route handlers are not permitted.

### Skill Registry

| Skill | File | Category | Approved Providers |
|---|---|---|---|
| NSW OC Question Generation | `skills/nsw-oc-question-generation.md` | A (admin) | Any |
| NSW Selective Question Generation | `skills/nsw-selective-question-generation.md` | A (admin) | Any |
| Writing Assessment | `skills/writing-assessment.md` | B (student) | Production Approved only |
| Question Quality Review | `skills/question-quality-review.md` | A (admin) | Any |
| AI Question Generation (general) | `skills/ai-question-generation.md` | A (admin) | Any |

---

## 7. AI Privacy Rules

### Allowed in AI Payloads

The following are permitted:

- Prompt text (question or writing prompt)
- Student response text (writing content — for writing assessment only)
- Rubric or marking criteria
- Year level (e.g., Year 5)
- Exam type (e.g., OC, Selective)
- Topic or subject label
- Question difficulty
- Generic performance pattern (e.g., percentage correct by topic)
- Anonymized question IDs

### Prohibited from AI Payloads

The following must never be included:

- Student full name
- Student date of birth
- Parent name or identity
- Parent email address
- Billing or payment information
- Subscription plan details
- Contact details of any kind
- School name or location
- Any combination of fields that could re-identify a student

### Privacy Audit

All AI requests are logged in `AIUsageLog` with a `payload_contained_student_data` boolean. Category B requests must set this flag to `true`. A monthly audit should confirm no PII appears in Category B payloads.

---

## 8. AI Generated Content Policy

AI-generated content is always a draft. The mandatory workflow is:

```
Draft (AI generated)
  ↓
Review (admin mandatory — no exceptions)
  ↓
Approved
  ↓
Published
```

Auto-publishing is not permitted for any AI-generated content. This applies to questions, explanations, and OCR-extracted structures.

---

## 9. Writing Assessment Disclaimer

All writing feedback generated by AI must be accompanied by the following disclaimer in every UI surface:

> "Writing feedback is educational guidance and does not represent official Selective School marking."

This disclaimer is non-negotiable. It must not be hidden, minimised, or removed.

---

## 10. Logging

AI usage is logged in `AIUsageLog`:

- Provider name
- Skill or feature invoked
- User or admin scope
- Token estimate (input and output)
- Error status
- Cost estimate
- `payload_contained_student_data` boolean

Raw prompt text must not be logged unless explicitly required for debugging and protected by admin-only access controls.

---

## 11. Premium Gating

AI features are Premium-only unless limited trial usage is configured.

Examples:

- Limited free AI explanation views per month
- Limited practice recommendations per week
- Writing feedback available to premium subscribers only

---

## 12. Non-Goals for MVP

- Fully autonomous AI tutoring without guardrails.
- AI-generated content auto-publishing.
- AI long-answer marking for HSC.
- Autonomous writing assessment without admin-configured rubric.
- Real-time AI-powered adaptive question selection during an exam session.
