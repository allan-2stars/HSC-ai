# HSC-AI Platform — Principal Architect Review
**Date:** 2026-06-01
**Status:** Pre-implementation. No code exists. Review based on stated requirements and DESIGN.md.
**Reviewed by:** Principal Software Architect (AI-assisted)

---

## Document State Warning

At the time of this review, the following referenced documentation files **do not exist**:

- CLAUDE.md
- CODEX.md
- docs/PRD.md
- docs/DESIGN.md (exists as root DESIGN.md — wrong path)
- docs/ARCHITECTURE.md
- docs/DATA_MODEL.md
- docs/EXAM_ENGINE.md
- docs/OCR_IMPORT_PIPELINE.md
- docs/AI_PROVIDER_STRATEGY.md
- docs/SUBSCRIPTION_MODEL.md
- docs/SECURITY_PRIVACY.md
- docs/ADMIN_CONTENT_WORKFLOW.md
- docs/ROADMAP.md
- docs/OPEN_DECISIONS.md
- skills/*.md

Only `README.md` (empty) and `DESIGN.md` (root-level design system) exist in the repository.

**This absence is itself a critical finding.** All architectural decisions in this document are proposals based on requirements stated in conversation. They have not been committed to authoritative documentation.

---

# Executive Summary

This project is architecturally ambitious, product-clear, and documentation-empty. The vision is coherent: a timed exam simulator for NSW OC/Selective preparation with admin-curated content, parent-owned accounts, and multi-provider AI. However, at the point of this review, **zero architectural decisions have been committed to documentation**, every referenced spec file is missing, and three critical problems have not been confronted:

1. **Copyright.** Reproducing or algorithmically mimicking NSW DoE exam content in a commercial product without clearance is a legal exposure that could terminate the business.
2. **Student authentication.** No one has specified how a 10-year-old logs in. This is not a detail — it determines the entire auth model.
3. **PaddleOCR on ARM64 is feasible but expensive.** The OCR worker will require ~1.5GB RAM on its own and will not build from PyPI wheels; it needs a custom Dockerfile.

The architecture proposed in prior conversations (Vercel + Supabase + Next.js monolith) is **incompatible** with the stated development constraints (Docker Compose, ARM64, self-hosted, Raspberry Pi 5). This review replaces that proposal entirely.

**Development environment constraints confirmed:**
- Raspberry Pi 5 (ARM64) as primary development and production target
- Docker Compose orchestration, mandatory
- Cloudflare Tunnel for external exposure
- Self-hosted: PostgreSQL, Redis, MinIO, PaddleOCR
- No managed cloud services as primary dependencies
- No Kubernetes, no AWS/Azure/GCP-specific services

**Preferred stack confirmed:**
- Backend: FastAPI
- Frontend: Next.js
- ORM: SQLAlchemy
- Auth: JWT + refresh token
- Storage: MinIO
- OCR: PaddleOCR (with caveats — see OCR Review)
- Testing: mandatory
- Monorepo: preferred

---

# Product Review

## Target Audience Assessment

**Stated:** Parents of NSW Year 4–6 students preparing for OC/Selective tests.

**Unstated but critical:**

- Students are aged 9–12. They likely do not have personal email accounts. The current parent/student model assumes students are represented by profiles under a parent account — but how does a student actually interact with the platform? No login mechanism is specified for students. This is a showstopper UX gap.

- The OC test is sat in Year 4 (for Year 5 entry) and the Selective test in Year 6. These are annual cohort events. This means **demand is highly seasonal** — spiking in Term 2–3, dead in Term 4. Subscription pricing and server capacity planning must account for this.

- The realistic total addressable market is ~15,000 OC applicants and ~20,000 Selective applicants per year in NSW, with significant tutor-industry competition (Matrix, Talented Students, etc.). Pricing pressure will be real.

## Business Model Gaps

- **No tier definitions exist.** "Free trial → paid" is mentioned but no prices, limits, or feature gates are documented. Before a single subscription table is designed, these must be explicit.

- **The 3-student limit** — is this a monetisation lever (pay for more students) or a technical constraint? If it's monetisation, there should be a 4+ tier. If it's technical, it's an artificial cap that will generate support tickets.

- **Group/tutoring centre use case is unaddressed.** Tutors will want to assign practice sets to 10–30 students. If you haven't designed for this, they'll build workarounds (one parent account per student) and you'll lose the most valuable segment. You don't need to build it in V1, but the data model must not make it impossible.

## Parent/Student Workflow Gaps

**The student authentication problem is the most critical unresolved product question.**

Three viable options exist, each with different implications:

| Option | Mechanism | Implications |
|--------|-----------|--------------|
| A — Device handoff | Parent logs in, selects student, hands device | No student credentials needed. But parent must be present. |
| B — Student PIN | Parent creates a 4–6 digit PIN per student | Simple for kids. PIN must be treated as a credential; reset flow needed. |
| C — Student link | Parent generates a session URL/QR code per student | Disposable session. Stateless but less trackable. |

**Option B is the correct choice.** Children aged 9–12 cannot reliably manage passwords. A PIN under the parent account, with the parent as the sole account owner, satisfies both usability and the Australian Privacy Act requirement that parental consent govern child data.

This must be designed before the auth schema is finalised.

## Admin Workflow Gaps

- **Who is "admin"?** Is this the founder manually reviewing questions? A team? If it's one person, a simple role gate is fine. If it's a team, you need admin sub-roles (content-creator vs. content-reviewer to prevent self-approval).

- **No SLA for the review queue.** A question in `pending_review` with no assigned reviewer sits forever. You need either auto-assignment or a notification system for the review queue.

- **No bulk operations defined.** Uploading a 50-question paper via OCR and reviewing each question one-by-one is unusable. Bulk approve/reject is mandatory for the OCR workflow.

---

# Content Architecture Review

## The Core Structural Question: Three Separate Entities

**Current assumption (from prior discussion):** Questions exist in a flat bank. Exam sets are curated collections.

**This is insufficient for this domain.** The OC/Selective context has three fundamentally different content types with different legal, operational, and UX properties:

```
┌──────────────────────────────────────────────────────────────────┐
│  TYPE 1: Question Bank (atomic, reusable, internally authored)   │
│  - Admin-written or AI-generated (always reviewed)               │
│  - Tagged by topic, difficulty, year level                       │
│  - Reusable across multiple practice sets                        │
│  - You OWN these                                                 │
├──────────────────────────────────────────────────────────────────┤
│  TYPE 2: Official Exam Papers (historical, structured as-is)     │
│  - Exact reproductions or close adaptations of past papers       │
│  - Presented as a complete paper, not shuffled                   │
│  - Question order and paper structure are part of the content    │
│  - COPYRIGHT RISK — you may NOT own these                        │
├──────────────────────────────────────────────────────────────────┤
│  TYPE 3: Practice Sets (curated, mixed, configurable)            │
│  - Drawn from the Question Bank                                  │
│  - Admin-assembled or rule-based                                 │
│  - May simulate an exam format without being tied to one paper   │
│  - You OWN these                                                 │
└──────────────────────────────────────────────────────────────────┘
```

**Why this separation matters architecturally:**

- Question Bank questions are atomic and reusable. A single question can appear in 10 practice sets.
- Official Exam Papers have a fixed ordering, a specific year/series identifier, and copyright attribution. They cannot be atomised and reshuffled.
- Practice Sets are compositions of Question Bank questions. They need their own metadata.

**If you treat all three as the same `questions` table with `exam_sets`, you will run into:**
- Inability to attribute official papers without corrupting the question bank
- Inability to lock paper question order vs. shuffle practice questions
- Copyright attribution becoming impossible at query time

**Proposed separation:**
```
question_bank         (atomic, authored, owned by platform)
    ↓ referenced by
practice_sets → practice_set_questions (junction, with sort_order)

exam_papers           (official papers, sequence-locked)
    → exam_paper_sections
        → exam_paper_questions (fixed ordering, copyright attribution)
```

## Copyright Risk — CRITICAL

The NSW Department of Education publishes past OC and Selective test papers. Using them commercially:

| Use | Legal Status |
|-----|-------------|
| Direct reproduction (scanning + uploading) | Copyright infringement. NSW DoE holds copyright. Commercial use requires licence. |
| Close paraphrase (changing names/numbers) | Likely infringement under Australian Copyright Act 1968, s 36. |
| Independently authored similar-style questions | Legal, provided specific questions are not copied. |
| AI-generated questions using official papers as prompts | Grey area. Do not use official papers as AI prompts without legal advice. |

**This is not a technical risk. It is a business-ending legal risk if not addressed before launch.**

Recommended actions before V1:
1. Obtain legal advice on what constitutes acceptable "style" vs. "copy" for OC/Selective questions.
2. Establish a clear policy: the Question Bank contains only admin-authored or admin-reviewed AI-generated questions.
3. If offering historical papers, obtain a licence or structure it as links to the NSW DoE website.
4. Never store OCR'd official paper content as `status=approved` questions in the question bank without copyright clearance.

---

# Exam Engine Review

## Browser-Based Exam Limitations — Honest Assessment

The stated requirements include "fullscreen/kiosk-like behavior, no copy/paste, tab switch detection." Each of these has hard technical limits on the web platform:

| Feature | Web API | Limitation |
|---------|---------|------------|
| Fullscreen | `requestFullscreen()` | Requires user gesture. Can be exited with `Esc` at any time. Cannot prevent exit. |
| Copy prevention | `oncopy` / `oncontextmenu` | Bypassable in seconds via DevTools console. Not a security control. |
| Paste prevention | `onpaste` | Same — ineffective against DevTools. |
| Tab switch detection | Page Visibility API | Detects tab switches and window minimise. Does NOT detect: OS window switching, split-screen, second monitor, phone camera. |
| Kiosk mode | None available via browser JS | True kiosk requires Electron, a native app, or browser kiosk flags at OS level. |

**Recommendation:** Reframe the exam engine as **"Exam Simulation Mode"** not **"Secure Exam Mode."** The platform deters casual cheating but does not prevent determined cheating. This is appropriate for exam preparation — it trains good exam habits. Claiming otherwise is misleading to parents and creates liability.

**Document this explicitly in the product:**
> "HSC-AI Exam Mode simulates exam conditions to help students develop time management and focus. It is not a secure exam system."

## Timer Architecture

The client-side timer synced every 30 seconds (prior proposal) has failure modes:
- Client clock drift (especially on mobile)
- User changes device system clock mid-exam
- Network loss during sync window loses answer state

**Correct approach:**
- Server stores `started_at` as `timestamptz` (UTC)
- `time_remaining = time_limit - (now() - started_at)` computed server-side on every API call
- Client displays a countdown derived from this server value
- Answers submitted per-question (not batched) — network loss only loses the current in-progress answer
- Heartbeat every 60 seconds to update `last_seen_at` for session health
- All timestamps UTC. Never `timestamp without time zone`.

## Immutability — Must Be Enforced at Database Level

Without a DB trigger, a bug in application code can silently update a submitted attempt:

```sql
CREATE OR REPLACE FUNCTION deny_attempt_modification()
RETURNS TRIGGER AS $$
BEGIN
  IF OLD.submitted_at IS NOT NULL THEN
    RAISE EXCEPTION 'Attempt % is submitted and cannot be modified', OLD.id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER protect_submitted_attempts
BEFORE UPDATE ON attempts
FOR EACH ROW EXECUTE FUNCTION deny_attempt_modification();
```

This trigger must be part of the initial migration. It cannot be added later when live data exists.

Additionally: **revoke DELETE permission on the `attempts` table** from the application database user. The app user should have `INSERT` and limited `UPDATE` only while `submitted_at IS NULL`.

## Edge Cases Not Addressed in Current Design

1. **Browser closed mid-exam** — Is the attempt abandoned or resumable? No `status` exists for "in progress, resumable." Need explicit resume handling.
2. **Subscription expires mid-exam** — Can the student complete the current session? Recommendation: yes (honour in-flight sessions), block new starts only.
3. **Double submission** — Client submits, receives 500 error, retries. Double-submission must be idempotent. Session token must be checked atomically on the server.
4. **Device handoff mid-exam** — Same session token used on a different device. Should this be blocked? Define the policy.
5. **Timezone** — All timestamps must be `timestamptz` (UTC). Never `timestamp` without timezone.

---

# Data Model Review

## Critical Missing Entity: Student Credentials

There is no `student_sessions` or `student_pins` table in the current model. This is a blocking schema gap.

```sql
CREATE TABLE student_credentials (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id    uuid NOT NULL UNIQUE REFERENCES students(id) ON DELETE CASCADE,
  pin_hash      text NOT NULL,     -- bcrypt hash of 4-6 digit PIN
  last_login_at timestamptz,
  created_at    timestamptz DEFAULT now()
);
```

Student sessions are child sessions under the parent's account. They must have limited scope: can take exams, cannot view billing, cannot manage account settings.

## Missing Entity: Attempt Resume State

Separates mutable in-progress state from the immutable final record:

```sql
CREATE TABLE attempt_sync (
  attempt_id        uuid PRIMARY KEY REFERENCES attempts(id) ON DELETE CASCADE,
  last_synced_at    timestamptz NOT NULL DEFAULT now(),
  answers_snapshot  jsonb NOT NULL,  -- current answer state between heartbeats
  time_remaining    integer NOT NULL
);
```

## Full Proposed Schema

```sql
-- Auth extended
CREATE TABLE public.parents (
  id            uuid PRIMARY KEY,  -- references Supabase auth.users OR internal users table
  full_name     text NOT NULL,
  phone         text,
  organization_id uuid REFERENCES organizations(id),  -- nullable, for future school/tutor use
  created_at    timestamptz DEFAULT now()
);

CREATE TABLE public.admins (
  id            uuid PRIMARY KEY,
  full_name     text NOT NULL,
  created_at    timestamptz DEFAULT now()
);

-- Future-proofing: nullable org column costs nothing in V1
CREATE TABLE public.organizations (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name        text NOT NULL,
  type        text NOT NULL CHECK (type IN ('tutoring_centre', 'school', 'individual')),
  created_at  timestamptz DEFAULT now()
);

CREATE TABLE public.students (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  parent_id     uuid NOT NULL REFERENCES public.parents(id) ON DELETE CASCADE,
  full_name     text NOT NULL,
  year_level    smallint NOT NULL CHECK (year_level BETWEEN 4 AND 6),
  date_of_birth date,      -- optional; year_level is the primary classifier
  avatar_seed   text,
  created_at    timestamptz DEFAULT now()
  -- 3-student limit enforced at API layer with row-lock transaction; CHECK constraint is defense-in-depth only
);

CREATE TABLE public.student_credentials (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id    uuid NOT NULL UNIQUE REFERENCES students(id) ON DELETE CASCADE,
  pin_hash      text NOT NULL,
  last_login_at timestamptz,
  created_at    timestamptz DEFAULT now()
);

CREATE TABLE public.subscriptions (
  id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  parent_id               uuid NOT NULL UNIQUE REFERENCES parents(id),
  stripe_customer_id      text UNIQUE,
  stripe_subscription_id  text UNIQUE,
  tier                    text NOT NULL DEFAULT 'free'
    CHECK (tier IN ('free', 'monthly', 'annual')),
  status                  text NOT NULL DEFAULT 'trialing'
    CHECK (status IN ('trialing', 'active', 'past_due', 'cancelled', 'paused')),
  current_period_start    timestamptz,
  current_period_end      timestamptz,
  created_at              timestamptz DEFAULT now(),
  updated_at              timestamptz DEFAULT now()
);

CREATE TABLE public.subjects (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name          text NOT NULL UNIQUE,
  exam_type     text NOT NULL CHECK (exam_type IN ('oc', 'selective', 'both')),
  display_order smallint DEFAULT 0
);

CREATE TABLE public.topics (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  subject_id  uuid NOT NULL REFERENCES subjects(id),
  name        text NOT NULL,
  slug        text NOT NULL UNIQUE
);

-- Question state machine
CREATE TYPE question_status AS ENUM (
  'draft',
  'pending_ocr',
  'ocr_failed',
  'needs_review',
  'in_review',
  'approved',
  'rejected',
  'archived'
);
CREATE TYPE question_source AS ENUM ('manual', 'ocr', 'ai_generated');
CREATE TYPE question_type AS ENUM ('mcq', 'short_answer', 'extended_response');

CREATE TABLE public.questions (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  subject_id          uuid NOT NULL REFERENCES subjects(id),
  topic_id            uuid REFERENCES topics(id),
  question_type       question_type NOT NULL DEFAULT 'mcq',
  difficulty          smallint NOT NULL DEFAULT 3 CHECK (difficulty BETWEEN 1 AND 5),
  year_level          smallint CHECK (year_level BETWEEN 4 AND 6),
  content             jsonb NOT NULL,
  -- MCQ shape: { "stem": "...", "options": ["A","B","C","D"], "correct_index": 2, "explanation": "..." }
  -- Enforced by Pydantic on write; DB has CHECK (content ? 'stem')
  source              question_source NOT NULL DEFAULT 'manual',
  status              question_status NOT NULL DEFAULT 'draft',
  review_note         text,
  claimed_by          uuid REFERENCES admins(id),  -- for in_review state
  created_by          uuid NOT NULL REFERENCES admins(id),
  reviewed_by         uuid REFERENCES admins(id),
  reviewed_at         timestamptz,
  created_at          timestamptz DEFAULT now(),
  updated_at          timestamptz DEFAULT now(),
  CONSTRAINT content_has_stem CHECK (content ? 'stem' AND length(content->>'stem') > 0)
);

-- Questions are IMMUTABLE once approved (enforced by trigger in migration)

CREATE TABLE public.question_media (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  question_id   uuid NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
  storage_path  text NOT NULL,  -- MinIO path, accessed via signed URL only
  media_type    text NOT NULL CHECK (media_type IN ('image', 'audio')),
  caption       text,
  sort_order    smallint DEFAULT 0
);

-- Practice Sets (Type 3 content — drawn from question_bank)
CREATE TABLE public.practice_sets (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title           text NOT NULL,
  description     text,
  subject_id      uuid REFERENCES subjects(id),
  year_level      smallint CHECK (year_level BETWEEN 4 AND 6),
  exam_type       text NOT NULL CHECK (exam_type IN ('oc', 'selective', 'practice')),
  time_limit_secs integer,  -- null = untimed
  is_published    boolean NOT NULL DEFAULT false,
  created_by      uuid NOT NULL REFERENCES admins(id),
  created_at      timestamptz DEFAULT now()
);

CREATE TABLE public.practice_set_questions (
  practice_set_id uuid NOT NULL REFERENCES practice_sets(id) ON DELETE CASCADE,
  question_id     uuid NOT NULL REFERENCES questions(id),
  sort_order      smallint NOT NULL,
  PRIMARY KEY (practice_set_id, question_id)
  -- Only approved questions allowed: enforced at API layer
);

-- Official Exam Papers (Type 2 — separate to preserve copyright attribution and fixed ordering)
CREATE TABLE public.exam_papers (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title           text NOT NULL,
  year            smallint,      -- e.g. 2023
  series          text,          -- e.g. 'OC Test', 'Selective'
  copyright_note  text,          -- attribution required for licensed content
  is_published    boolean NOT NULL DEFAULT false,
  created_by      uuid NOT NULL REFERENCES admins(id),
  created_at      timestamptz DEFAULT now()
);

CREATE TABLE public.exam_paper_questions (
  paper_id        uuid NOT NULL REFERENCES exam_papers(id) ON DELETE CASCADE,
  question_id     uuid NOT NULL REFERENCES questions(id),
  section         text,
  sort_order      smallint NOT NULL,
  PRIMARY KEY (paper_id, question_id)
);

-- Attempts
CREATE TABLE public.attempts (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id            uuid NOT NULL REFERENCES students(id),
  practice_set_id       uuid REFERENCES practice_sets(id),
  exam_paper_id         uuid REFERENCES exam_papers(id),
  session_token         text UNIQUE,  -- cleared on submit
  started_at            timestamptz NOT NULL DEFAULT now(),
  submitted_at          timestamptz,  -- null = in progress
  time_remaining_secs   integer,      -- snapshot at submit
  score_raw             integer,
  score_pct             numeric(5,2),
  tab_switch_count      smallint DEFAULT 0,
  fullscreen_exit_count smallint DEFAULT 0,
  is_complete           boolean NOT NULL DEFAULT false,
  created_at            timestamptz DEFAULT now(),
  CONSTRAINT attempt_references_one
    CHECK (
      (practice_set_id IS NOT NULL AND exam_paper_id IS NULL) OR
      (practice_set_id IS NULL AND exam_paper_id IS NOT NULL)
    )
);

-- Immutability trigger applied in migration (see Exam Engine section)

CREATE TABLE public.attempt_sync (
  attempt_id        uuid PRIMARY KEY REFERENCES attempts(id) ON DELETE CASCADE,
  last_synced_at    timestamptz NOT NULL DEFAULT now(),
  answers_snapshot  jsonb NOT NULL,
  time_remaining    integer NOT NULL
);

CREATE TABLE public.attempt_answers (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  attempt_id        uuid NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
  question_id       uuid NOT NULL REFERENCES questions(id),
  selected_index    smallint,
  text_response     text,
  was_correct       boolean,      -- denormalised at submit time for analytics query performance
  answered_at       timestamptz NOT NULL DEFAULT now(),
  time_spent_secs   integer,
  UNIQUE (attempt_id, question_id)
);

CREATE TABLE public.attempt_events (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  attempt_id  uuid NOT NULL REFERENCES attempts(id),
  event_type  text NOT NULL
    CHECK (event_type IN ('tab_switch', 'fullscreen_exit', 'paste_attempt', 'copy_attempt')),
  occurred_at timestamptz NOT NULL DEFAULT now(),
  metadata    jsonb
);

-- Import Jobs
CREATE TYPE import_status AS ENUM ('queued', 'processing', 'ocr_failed', 'needs_review', 'completed', 'failed');

CREATE TABLE public.import_jobs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  type            text NOT NULL CHECK (type IN ('ocr', 'ai_generated')),
  status          import_status NOT NULL DEFAULT 'queued',
  source_path     text,         -- MinIO path for OCR source file
  ai_prompt       text,
  draft_questions jsonb,        -- extracted drafts before DB insertion
  created_by      uuid NOT NULL REFERENCES admins(id),
  completed_at    timestamptz,
  error_message   text,
  created_at      timestamptz DEFAULT now()
);

-- Refresh tokens
CREATE TABLE public.refresh_tokens (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL,
  token_hash  text NOT NULL UNIQUE,
  expires_at  timestamptz NOT NULL,
  revoked     boolean NOT NULL DEFAULT false,
  created_at  timestamptz DEFAULT now()
);
```

## Entity Relationship Summary

```
parents ──► subscriptions (1:1)
  │  └──► organization (optional, future)
  └──► students (max 3)
         ├──► student_credentials (PIN)
         └──► attempts
                ├──► attempt_sync (mutable, in-progress state)
                ├──► attempt_answers
                └──► attempt_events

admins
  ├──► questions ──► question_media
  ├──► practice_sets ──► practice_set_questions → questions
  ├──► exam_papers ──► exam_paper_questions → questions
  └──► import_jobs

subjects ──► topics → questions
```

## Multi-Tenancy / School Support

**The current model (parent → students → attempts) is single-tenant.** Adding school/tutor support later requires an `organizations` table retrofitted onto a live schema.

**Recommendation: Add `organization_id uuid REFERENCES organizations(id)` as a nullable column on `parents` now.** This column is `NULL` for all V1 users. Zero operational overhead. Eliminates a painful migration later.

## Question Versioning Policy

Once a question is `approved`, it is referenced by practice sets and student attempts. If an admin edits it, existing attempt results reference a different question than the student actually saw.

**Decision for V1: Questions are immutable once approved.** To fix an error:
1. Archive the old question (`status = archived`)
2. Create a new question with the correction
3. Update practice sets to reference the new question

This is the simpler, correct choice for V1. A version-history table is a V2+ feature.

---

# Analytics Review

## V1: Rule-Based Only

The instinct to use AI for recommendations is premature. The dataset will be tiny at launch. AI recommendations on small datasets produce noise. Every V1 analytical feature must be rule-based:

| Feature | V1 Implementation | When to Add AI |
|---------|------------------|----------------|
| Weakness detection | Topics with <50% correct rate over last 10 attempts | When ≥500 attempts per subject |
| Progress tracking | Attempt score over time (line chart) | After 6+ months of longitudinal data |
| Time management | Avg time per question vs. target time | — |
| Subject breakdown | Correct % by subject/topic (bar chart) | — |
| Comparative performance | Percentile within platform cohort | After ≥200 active students |

## Recommended MVP Analytics (3 metrics only)

These are SQL queries. No AI required. No ML models. No training data:

1. **Score trend** — Last 5 attempts per subject, line chart
2. **Weakest 3 topics** — Ordered by error rate across all attempts
3. **Time vs. score** — Is the student rushing (low time, low score) or overthinking (high time, average score)?

## When to Add AI Recommendations

Not before:
- ≥500 student-attempts per subject
- ≥6 months of longitudinal data
- A validated mapping of question-topic to curriculum standards

---

# AI Architecture Review

## Provider Abstraction Interface

The active provider is selected via `AI_PROVIDER=openai|anthropic|ollama` environment variable. Factory pattern in the service layer. Defined as a Python Protocol:

```python
from typing import Protocol
from dataclasses import dataclass

@dataclass
class QuestionDraft:
    stem: str
    options: list[str]
    correct_index: int
    explanation: str
    subject: str
    topic: str
    year_level: int
    difficulty: int  # 1-5, AI estimate; overridable by admin

class AIProvider(Protocol):
    async def generate_questions(
        self,
        subject: str,
        topic: str,
        year_level: int,
        count: int,
        difficulty: int,
    ) -> list[QuestionDraft]: ...

    async def improve_question(
        self,
        draft: QuestionDraft,
        feedback: str,
    ) -> QuestionDraft: ...

    async def health_check(self) -> bool: ...
```

## Critical Distinction: Admin AI vs. Student AI

There are two completely different AI use cases with different data sensitivity levels. **The current design conflates them. They must be separated.**

| Use Case | Data Involved | Safe Providers |
|----------|--------------|----------------|
| Admin question generation | No student data. Admin prompt only. | Any provider |
| Student adaptive recommendations (future) | Student attempt history, performance, age | Ollama (local) only, or fully anonymised |

**Never send student data to external AI providers.** This is a privacy violation under APP 6 (Australian Privacy Act 1988) without explicit consent and a data processing agreement.

## Provider Risk Assessment

| Provider | Commercial Risk | Privacy Risk (Student Data) | ARM64 Local | V1 Recommendation |
|----------|----------------|----------------------------|-------------|-------------------|
| OpenAI | API ToS restricts under-13 use without parental consent | HIGH — do not send student data | No | Admin-only question generation |
| Anthropic (Claude) | No training on API data by default | MEDIUM | No | Preferred; admin-only |
| DeepSeek | Data stored in China under PRC law | CRITICAL — PRC data localisation | No | **Remove from V1** |
| Gemini | Google data practices | HIGH | No | Not recommended for V1 |
| Ollama | Fully local, no data egress | NONE | ARM64 compatible | Best for privacy; dev/offline use |
| OpenRouter | Routes to multiple providers; unclear data handling | HIGH | No | Not recommended for V1 |

## DeepSeek — Must Be Removed from V1

DeepSeek's obligations under PRC law (data localisation, government access upon request) are irreconcilable with the Australian Privacy Act APP 8 requirements for overseas disclosure of personal information. Even for admin-only question generation, the commercial and reputational risk of being associated with data flowing to China in an education platform for children is unacceptable.

Remove from V1. Document the decision. Can be revisited in future for admin-only, no-student-data use cases with a legal disclaimer.

## Ollama on Raspberry Pi 5 — Realistic Assessment

| Model | RAM Required | Pi 5 (8GB) Feasibility | Notes |
|-------|-------------|----------------------|-------|
| llama3.2:3b | ~2.5GB | Feasible | Poor structured output |
| qwen2.5:7b | ~5GB | Tight | Better structured output |
| llama3.1:8b | ~5GB | Tight | Acceptable quality |

Running a 7B model on Pi 5 while also running PostgreSQL, Redis, FastAPI, Next.js, and PaddleOCR **is not feasible simultaneously on 8GB RAM**. Total would exceed available memory.

**Decision: Ollama is for development/offline use only. Not a production AI target for V1.** Use OpenAI or Anthropic for admin-only production question generation.

---

# OCR Review

## PaddleOCR on ARM64 — Honest Assessment

| Dimension | Assessment |
|-----------|------------|
| ARM64 support | Exists but requires `paddlepaddle/paddle:2.6.1-cpu-arm64` base image (no PyPI wheels) |
| Docker image build time on Pi 5 | 45–90 minutes from source |
| Runtime RAM | 1.2–2GB per worker process |
| Processing time (Pi 5, CPU only) | 5–20 seconds per page |
| Model download on first run | ~100MB |
| Accuracy for printed text | Good |
| Accuracy for maths notation | **FAILS** — fractions, exponents, geometry diagrams not handled |
| ARM64 Docker base image | `paddlepaddle/paddle:2.6.1-cpu-arm64` — use this, not a standard Python image |

**For OC/Selective maths content, PaddleOCR alone is insufficient.**

**Recommended dual-OCR approach:**

| Content Type | OCR Engine | Rationale |
|-------------|-----------|-----------|
| English / Reading / General Ability | PaddleOCR | Good printed text accuracy |
| Mathematics (fractions, equations, geometry) | Pix2Text | Open source, ARM64 compatible, outputs LaTeX for maths notation |

Pix2Text is available on PyPI, has ARM64 support via PyTorch, and handles mixed text + maths formula extraction. Use it for any question containing mathematical notation.

## Extended OCR Question States

The proposed `draft → pending_review → approved/rejected` is insufficient for the OCR workflow:

| State | Meaning |
|-------|---------|
| `draft` | Manually created by admin |
| `pending_ocr` | OCR job queued or running |
| `ocr_failed` | OCR could not extract content; needs manual intervention |
| `needs_review` | OCR completed, draft created, awaiting admin review |
| `in_review` | Claimed by a specific admin (prevents concurrent review conflicts) |
| `approved` | Published, usable in practice sets |
| `rejected` | Rejected with reason; can be edited and resubmitted |
| `archived` | Removed from active pool |

## OCR Workflow Failure Modes

| Stage | Failure | Mitigation |
|-------|---------|------------|
| Upload | Corrupted/unsupported file | Validate PDF/PNG/JPG before queuing; reject other formats at API boundary |
| OCR processing | Worker crashes (OOM on Pi) | ARQ retry with exponential backoff; max 3 retries; store error in `import_jobs.error_message` |
| OCR output | Poor quality scan → garbled text | Quality score threshold: confidence < 70% → flag `ocr_failed`, not `needs_review` |
| Admin review | Admin approves incorrect question | No automated prevention; review workflow is the only gate; log `reviewed_by` for audit |
| Diagram in question | OCR extracts text only | Flag questions with detected image regions as `contains_visual`; admin must attach diagram image manually |

## Task Queue for OCR and AI Workers

OCR and AI generation are CPU/network-bound tasks unsuitable for FastAPI background tasks (which block the event loop and don't survive worker restarts).

**Recommended: ARQ (Async Redis Queue)**
- Lighter footprint than Celery (no prefork workers, pure asyncio)
- Works with existing Redis instance
- Survives Pi restarts (jobs persist in Redis)
- ARM64 compatible (pure Python)

Worker runs as a separate Docker service: `docker-compose.yml` includes an `ocr-worker` container.

---

# Security Review

## Australian Privacy Act 1988 — Specific Requirements

This platform handles personal information of minors under 18. All 13 Australian Privacy Principles (APPs) apply:

| APP | Requirement | Current Gap |
|-----|-------------|-------------|
| APP 1 | Privacy policy must be openly available | No policy exists |
| APP 3 | Collect only what is necessary | Student DOB requested but year_level is sufficient for most purposes |
| APP 5 | Notify individuals of data collection at point of collection | No notification flow designed |
| APP 6 | Only use data for the primary purpose collected | Sending student data to external AI providers violates APP 6 |
| APP 8 | Overseas disclosure requires equivalent protection | DeepSeek (China) cannot receive student data. OpenAI/Anthropic require DPAs. |
| APP 11 | Protect personal information from misuse and loss | Encryption at rest, access logging required |
| APP 12 | Right to access personal data | Parent must be able to export all student data |
| APP 13 | Right to correct personal data | Parent must be able to edit/delete student profiles |

The Australian Children's Online Privacy Code (if enacted before launch) will add further requirements for platforms directed at children.

## JWT + Refresh Token Architecture for Self-Hosted Pi

| Token Type | Properties |
|-----------|-----------|
| Access token | 15-minute TTL, stateless JWT, signed RS256 (asymmetric) |
| Refresh token | 7-day TTL, stored in `refresh_tokens` PostgreSQL table, HttpOnly cookie only |
| Student session token | Derived from parent session + PIN verification; JWT with `sub=student:{id}`, `parent={parent_id}`, reduced scope |
| Admin token | 8-hour TTL, JWT with `role=admin`; no refresh token; re-authenticate each session |

**Never store JWTs in `localStorage`.** Always `HttpOnly` cookies. Next.js frontend uses server-side cookie handling.

## Data Residency

Self-hosted on Pi via Cloudflare Tunnel means:
- Data stays on the Pi (user's location, presumed Australia)
- Cloudflare acts as TLS termination proxy only
- **Disable Cloudflare caching, analytics, and Bot Fight Mode** on API routes — these could log student request metadata
- Use Cloudflare Zero Trust for admin routes

This is actually an excellent posture for Australian Privacy Act compliance: data does not leave Australian jurisdiction.

## MinIO Security Requirements

- Generate time-limited signed URLs for all question media (never permanent public URLs)
- A permanent URL to a question image allows subscription bypass (share the link externally)
- Signed URL expiry: 1 hour maximum
- MinIO buckets: private by default, no public read policy

## Application Database User Permissions

The FastAPI application should connect with a restricted database user:

```sql
-- Never grant these to the app user:
REVOKE DELETE ON attempts FROM app_user;
REVOKE DELETE ON attempt_answers FROM app_user;
REVOKE UPDATE ON attempts FROM app_user;  -- handled by trigger, belt-and-suspenders

-- Admin operations require elevated user or service account
```

---

# Readiness Assessment

| Dimension | Rating | Reason |
|-----------|--------|--------|
| **Product Readiness** | AMBER | Core concept is clear; student auth model, subscription tiers, and copyright policy are unresolved |
| **Architecture Readiness** | RED | No tech stack decisions are documented. Prior Vercel/Supabase proposal is incompatible with Docker/Pi constraints. |
| **Data Model Readiness** | AMBER | Solid proposal exists in this document but has not been reviewed or approved. Student credentials, attempt sync, and multi-tenancy hooks are missing from earlier proposals. |
| **Security Readiness** | RED | No privacy policy. No data processing agreements with AI providers. No documented APP compliance approach. Student auth model unresolved. |
| **MVP Readiness** | RED | Missing: student login, subscription tiers, copyright policy, exam engine spec, OCR approach for maths. Cannot safely start coding without these. |
| **Docker/Pi Readiness** | AMBER | Architecture is Pi-compatible but resource constraints (PaddleOCR + other services) need explicit planning. PaddleOCR ARM64 requires custom Dockerfile. |
| **Content Readiness** | RED | Copyright policy unresolved. No question bank. Admin content tool must be built first, before any student-facing feature. |

---

# Top 10 Risks

**RISK 1 — COPYRIGHT (Severity: CRITICAL / Probability: HIGH)**

Using OCR'd official NSW DoE exam papers commercially without a licence is copyright infringement. This risk alone can terminate the business.

*Action: Legal advice before any content ingestion. Document policy in writing.*

---

**RISK 2 — STUDENT AUTH UNDEFINED (Severity: HIGH / Probability: CERTAIN)**

No mechanism exists for a child to log in. The entire student-facing UX is blocked until this is resolved.

*Action: Decide on PIN-based student sessions this week. Design before any auth code is written.*

---

**RISK 3 — PI 5 MEMORY PRESSURE (Severity: HIGH / Probability: HIGH)**

PaddleOCR (1.2–2GB) + Ollama 7B (5GB) + PostgreSQL + Redis + FastAPI + Next.js exceeds 8GB RAM. Cannot run full stack simultaneously on a Pi 5.

*Action: PaddleOCR and Ollama cannot run simultaneously. Docker Compose profiles required. Resource limits (`mem_limit`) must be set per service.*

---

**RISK 4 — DEEPSEEK DATA SOVEREIGNTY (Severity: HIGH / Probability: CERTAIN)**

DeepSeek cannot be used with Australian student data under APP 8 (PRC data localisation law is irreconcilable with Australian Privacy Act overseas disclosure requirements).

*Action: Remove from V1 provider list entirely. Document the decision.*

---

**RISK 5 — EXAM INTEGRITY OVERCLAIMING (Severity: MEDIUM / Probability: HIGH)**

If marketing claims "kiosk-like" or "secure" exam mode, browser limitations create a false promise and potential liability.

*Action: Frame as "Exam Simulation Mode" in all copy. Document browser limitations explicitly.*

---

**RISK 6 — IMMUTABILITY NOT ENFORCED AT DB LEVEL (Severity: HIGH / Probability: HIGH)**

Without a DB trigger, a bug in application code can silently update a submitted attempt, corrupting the audit trail.

*Action: Immutability trigger must be in the initial database migration. Non-negotiable.*

---

**RISK 7 — JSONB CONTENT WITHOUT VALIDATION (Severity: MEDIUM / Probability: HIGH)**

Malformed question content (null stem, invalid options array) will silently pass DB constraints and corrupt the exam experience at runtime.

*Action: Pydantic schemas for all question types with strict validation on every FastAPI write endpoint.*

---

**RISK 8 — NO QUESTION BANK AT LAUNCH (Severity: HIGH / Probability: HIGH)**

The platform is worthless without content. Building the exam engine before having questions is wasted work that will block testing.

*Action: Admin content tool and question bank are Milestone 1. Exam engine is Milestone 2. This order is non-negotiable.*

---

**RISK 9 — SEASONAL DEMAND SPIKE (Severity: MEDIUM / Probability: CERTAIN)**

OC/Selective prep peaks sharply in NSW Term 2–3. Pi 5 as production server has a concurrency ceiling (~20 simultaneous active exams under typical load). Beyond that, response times degrade.

*Action: Load test the exam engine before launch. Define the concurrency ceiling. Have a documented fallback plan (upgrade to Pi 5 cluster or VPS migration).*

---

**RISK 10 — ADMIN SELF-REVIEW (Severity: MEDIUM / Probability: MEDIUM)**

If a single admin can create AND approve their own questions with no audit trail, quality control is fragile and OCR errors will reach students.

*Action: Log `created_by` and `reviewed_by` on every question. In V1, the same admin may do both, but this must be visible in the admin UI. Later: require different admins for creation and approval.*

---

# Required Decisions

**DECISION 1 — Student login mechanism**
Options: Device handoff / Student PIN / Session QR code
Recommendation: PIN-based student session under parent account
Blocking: Auth schema, JWT scope design, student UX

**DECISION 2 — Subscription tiers and pricing**
Required: Tier names, monthly price, free trial duration, feature gates, student limit per tier, whether 3-student cap is hard or a tier boundary
Blocking: Stripe integration, access control middleware

**DECISION 3 — Copyright policy for content**
Required: Legal advice on OC/Selective content. Document what can/cannot be ingested. Decide whether official papers will be offered.
Blocking: OCR pipeline design, content import workflow, content architecture

**DECISION 4 — Font: waldenburgNormal or Inter**
waldenburgNormal is proprietary. DESIGN.md documents Inter/Space Grotesk as the substitute. Commit to Inter now. Do not start building UI with an unlicensed font.
Blocking: Tailwind config, component library build

**DECISION 5 — Question versioning policy**
Options: Immutable once approved (recommended for V1) / Version history table
Recommendation: Immutable once approved; archive + recreate for corrections
Blocking: Question schema, migration design

**DECISION 6 — OCR approach for maths content**
Options: PaddleOCR only (fails on maths) / PaddleOCR + Pix2Text (dual engine)
Recommendation: Pix2Text for maths questions, PaddleOCR for English/GA
Blocking: OCR worker Dockerfile, import pipeline design

**DECISION 7 — AI provider for V1**
Recommendation: OpenAI or Anthropic for admin-only question generation. No AI provider for student-facing features in V1. DeepSeek removed.
Blocking: AIProvider interface spec, environment variable config, DPA agreements

**DECISION 8 — Official exam papers: in or out of V1**
If in: requires copyright clearance, separate data model, different UX
If out: simpler V1, focus on question bank only
Recommendation: Out of V1. Link to NSW DoE website for official papers.
Blocking: Content architecture, data model finalisation

**DECISION 9 — Admin team structure for V1**
Single admin (founder only) vs. multi-admin with roles
Recommendation: Single admin for V1, but log all review actions for future auditability
Blocking: Admin auth design, review workflow permissions

**DECISION 10 — Pi 5 production ceiling and fallback plan**
Pi 5 is suitable for ≤20 simultaneous exam sessions. Define the threshold and the failover plan before launch.
Blocking: Architecture design, capacity planning, Cloudflare Tunnel configuration

---

# Recommended Milestone 1

**Goal:** Admin can log in, create questions, review them, and publish a practice set. No student-facing features. No exam engine. No billing.

This is the only safe starting point. Without content, the exam engine has nothing to test against.

```
M1 — ADMIN CONTENT FOUNDATION (Target: 3 weeks)
═══════════════════════════════════════════════

Infrastructure:
  ✦ Monorepo scaffold with docker-compose.yml
  ✦ Services: postgres, redis, backend (FastAPI), frontend (Next.js), minio, nginx
  ✦ All ARM64-compatible base images confirmed and tested on Pi 5
  ✦ Alembic migrations initialised with full schema from this document
  ✦ GitHub Actions CI: tests + lint on push

Database (migrations only):
  ✦ All tables from schema above
  ✦ Immutability trigger on questions (approved → read-only)
  ✦ DB app user with revoked DELETE on questions and attempts
  ✦ Seed: subjects and topics for OC Mathematics and English

Auth (admin only in M1):
  ✦ POST /api/v1/auth/admin/login — JWT RS256, refresh token in postgres
  ✦ Admin route guard middleware (FastAPI dependency)
  ✦ Admin login page in Next.js (functional, no full design system yet)
  ✦ bootstrap script: scripts/create_admin.py

Question Bank (API + UI):
  ✦ Question CRUD: create, get, list (filterable), update (draft only)
  ✦ State transitions: submit, approve, reject
  ✦ Review queue endpoint
  ✦ Question list UI (table: status, subject, topic, difficulty, created_at)
  ✦ Question editor UI (MCQ only: stem, 4 options, correct answer, explanation)
  ✦ Review queue UI (one-by-one: see question, approve/reject with optional note)
  ✦ Subject + topic management UI (admin can add topics)

Media:
  ✦ MinIO configured, bucket created, lifecycle policies applied
  ✦ Image upload endpoint for questions (PNG/JPG, 5MB limit)
  ✦ Signed URL generation (1-hour expiry)
  ✦ Images displayed in question editor and review UI

Practice Sets (admin only, no student access yet):
  ✦ Practice set CRUD
  ✦ Add/remove approved questions to a set
  ✦ Publish/unpublish a set

Testing (mandatory):
  ✦ pytest: all API endpoints, ≥80% coverage
  ✦ State machine transition tests (cannot approve a draft, cannot edit approved)
  ✦ Immutability trigger test (verify DB raises exception on approved question update)
  ✦ Auth middleware tests (unauthenticated requests return 401)

M1 Gate Criteria (must all pass before M2 starts):
  □ Admin can log in
  □ Admin can create a 4-option MCQ question in Mathematics
  □ Admin can submit it for review
  □ Admin can approve it
  □ Approved question appears in question list with status=approved
  □ Approved question CANNOT be edited (trigger test passes)
  □ Admin can create a practice set with 5 approved questions
  □ All API endpoints have passing tests (≥80% coverage)
  □ docker-compose up starts all services cleanly on ARM64 Pi 5
  □ No service exceeds its Docker mem_limit during normal operation

NOT IN M1:
  ✗ Parent registration / login
  ✗ Student profiles or PIN login
  ✗ Exam engine (M2)
  ✗ OCR pipeline (M2)
  ✗ AI question generation (M2)
  ✗ Stripe billing (M3)
  ✗ Full design system polish (M2)
  ✗ Analytics (M3)
```

---

# Repository Structure

```
hsc-ai/
│
├── docker-compose.yml                  ← development: all services
├── docker-compose.prod.yml             ← production overrides (resource limits, restart policies)
├── docker-compose.override.yml         ← local developer overrides (gitignored)
├── .env.example                        ← all required env vars with descriptions
├── .env                                ← local values (gitignored)
├── Makefile                            ← shortcuts: make up, make down, make test, make migrate, make seed
│
├── backend/
│   ├── Dockerfile                      ← python:3.12-slim (ARM64 compatible)
│   ├── requirements.txt
│   ├── requirements-dev.txt            ← pytest, httpx, factory-boy, etc.
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/                   ← migration files (tracked in git)
│   └── app/
│       ├── main.py                     ← FastAPI app factory, lifespan handler
│       ├── core/
│       │   ├── config.py               ← pydantic-settings, all env var definitions
│       │   ├── security.py             ← JWT RS256 creation/validation, PIN hashing (bcrypt)
│       │   └── database.py             ← SQLAlchemy async engine, session factory
│       ├── api/
│       │   ├── deps.py                 ← FastAPI dependencies: get_db, get_current_admin, get_current_parent, get_current_student
│       │   └── v1/
│       │       ├── router.py           ← includes all sub-routers
│       │       ├── auth.py             ← login, logout, refresh, reset-password
│       │       ├── admin/
│       │       │   ├── questions.py    ← CRUD + state transitions
│       │       │   ├── practice_sets.py
│       │       │   ├── exam_papers.py
│       │       │   └── import_jobs.py
│       │       ├── parent/
│       │       │   ├── students.py
│       │       │   └── subscription.py
│       │       └── exam/
│       │           └── attempts.py     ← start, sync, submit, results
│       ├── models/                     ← SQLAlchemy ORM models
│       │   ├── user.py                 ← parents, admins, student_credentials, refresh_tokens
│       │   ├── content.py              ← questions, subjects, topics, media, practice_sets, exam_papers
│       │   ├── attempt.py              ← attempts, attempt_sync, attempt_answers, attempt_events
│       │   └── billing.py             ← subscriptions
│       ├── schemas/                    ← Pydantic v2 request/response models
│       │   ├── question.py             ← MCQContent, QuestionCreate, QuestionResponse (strict validation)
│       │   ├── attempt.py
│       │   ├── auth.py
│       │   └── subscription.py
│       ├── services/                   ← business logic, no FastAPI dependencies
│       │   ├── question_service.py     ← state machine, bulk operations
│       │   ├── exam_service.py         ← attempt creation, submission, scoring
│       │   ├── ai/
│       │   │   ├── base.py             ← AIProvider Protocol
│       │   │   ├── factory.py          ← provider selection via AI_PROVIDER env var
│       │   │   ├── openai_provider.py
│       │   │   ├── anthropic_provider.py
│       │   │   └── ollama_provider.py
│       │   └── ocr/
│       │       ├── base.py             ← OCRProvider Protocol
│       │       ├── factory.py          ← provider selection via OCR_PROVIDER env var
│       │       ├── paddleocr_provider.py
│       │       └── pix2text_provider.py
│       └── workers/                    ← ARQ task definitions
│           ├── ocr_worker.py           ← process_ocr_job task
│           └── ai_worker.py            ← generate_questions_job task
│
├── frontend/
│   ├── Dockerfile                      ← node:20-alpine (ARM64 compatible)
│   ├── package.json
│   ├── tailwind.config.ts              ← design tokens from DESIGN.md (Inter substituted for waldenburgNormal)
│   ├── next.config.ts                  ← API proxy to backend, image domains
│   └── src/
│       ├── app/
│       │   ├── (admin)/
│       │   │   ├── layout.tsx          ← admin shell, auth guard
│       │   │   ├── questions/
│       │   │   │   ├── page.tsx        ← question list
│       │   │   │   ├── new/page.tsx    ← question editor
│       │   │   │   └── [id]/page.tsx   ← question detail/edit
│       │   │   ├── review/
│       │   │   │   └── page.tsx        ← review queue
│       │   │   └── practice-sets/
│       │   ├── (parent)/
│       │   │   ├── layout.tsx
│       │   │   ├── dashboard/
│       │   │   └── students/
│       │   ├── (exam)/
│       │   │   └── [attemptId]/
│       │   │       └── page.tsx        ← exam engine (M2)
│       │   └── auth/
│       │       ├── login/
│       │       └── register/
│       ├── components/
│       │   ├── ui/                     ← primitive components (Button, Input, Card, Badge, Modal)
│       │   ├── admin/                  ← QuestionEditor, ReviewCard, StateChip, ImportJobStatus
│       │   ├── exam/                   ← ExamTimer, QuestionDisplay, AnswerSelector (M2)
│       │   └── parent/                 ← StudentCard, ProgressChart, AttemptHistory
│       └── lib/
│           ├── api.ts                  ← typed API client (fetch wrapper with auth headers)
│           └── auth.ts                 ← client-side session, JWT decode, role detection
│
├── workers/
│   ├── ocr/
│   │   ├── Dockerfile                  ← BASE: paddlepaddle/paddle:2.6.1-cpu-arm64
│   │   │                                  Installs: pix2text, arq, app.workers.ocr_worker
│   │   └── entrypoint.sh
│   └── ai/
│       ├── Dockerfile                  ← python:3.12-slim + openai + anthropic + arq
│       └── entrypoint.sh
│
├── nginx/
│   ├── nginx.conf                      ← /api/* → backend:8000, /* → frontend:3000
│   └── Dockerfile                      ← nginx:alpine (ARM64 compatible)
│
├── infra/
│   ├── cloudflare-tunnel.yml           ← tunnel config: routes to nginx:80
│   └── minio-init.sh                   ← creates 'questions' bucket with private policy on first run
│
├── docs/
│   ├── ARCHITECTURE_REVIEW.md          ← this file
│   ├── ARCHITECTURE.md                 ← to be written after decisions are finalised
│   ├── DATA_MODEL.md
│   ├── EXAM_ENGINE.md
│   ├── OCR_IMPORT_PIPELINE.md
│   ├── AI_PROVIDER_STRATEGY.md
│   ├── SUBSCRIPTION_MODEL.md
│   ├── SECURITY_PRIVACY.md
│   ├── ADMIN_CONTENT_WORKFLOW.md
│   ├── ROADMAP.md
│   └── OPEN_DECISIONS.md
│
├── scripts/
│   ├── seed_subjects.py                ← populates subjects and topics for OC/Selective
│   └── create_admin.py                 ← bootstraps first admin user (run once)
│
└── tests/
    ├── conftest.py                     ← pytest fixtures, test DB setup
    ├── backend/
    │   ├── test_auth.py
    │   ├── test_questions.py           ← state machine transitions, immutability
    │   ├── test_exam_engine.py         ← timer, submission, idempotency
    │   └── test_permissions.py         ← role guard: unauthenticated = 401, wrong role = 403
    └── integration/
        └── test_exam_flow.py           ← full end-to-end: create question → approve → practice set → attempt → submit
```

## docker-compose.yml Service Summary

```yaml
services:
  postgres:
    image: postgres:16-alpine       # ARM64 compatible
    mem_limit: 256m

  redis:
    image: redis:7-alpine            # ARM64 compatible
    mem_limit: 64m

  minio:
    image: minio/minio               # ARM64 compatible
    mem_limit: 256m

  backend:
    build: ./backend
    mem_limit: 256m
    depends_on: [postgres, redis, minio]

  ocr-worker:
    build: ./workers/ocr             # paddlepaddle/paddle:2.6.1-cpu-arm64 base
    mem_limit: 2048m                 # PaddleOCR + Pix2Text need headroom
    profiles: ["ocr"]               # only started when explicitly needed

  ai-worker:
    build: ./workers/ai
    mem_limit: 256m
    profiles: ["ai"]

  frontend:
    build: ./frontend
    mem_limit: 512m
    depends_on: [backend]

  nginx:
    build: ./nginx
    mem_limit: 32m
    ports: ["80:80"]
    depends_on: [backend, frontend]
```

Note the `profiles` on ocr-worker and ai-worker: `docker compose --profile ocr up` starts OCR processing; the default `docker compose up` does not start the heavy workers. This keeps the Pi 5 within memory budget for day-to-day development and exam serving.

---

# Features to Remove from V1

The following items are in scope in various planning documents or implied by requirements but should be explicitly deferred:

| Feature | Reason to Defer |
|---------|----------------|
| Ollama / local AI inference | Memory conflict with other services on 8GB Pi; use cloud AI (admin-only) instead |
| DeepSeek provider | Data sovereignty risk under Australian Privacy Act; not fixable in V1 |
| OpenRouter provider | Unclear data handling; no student data should transit a routing service |
| Short-answer / extended response questions | Requires AI-assisted marking; out of scope until M3+ |
| AI-powered student recommendations | Requires large dataset; use rule-based analytics until ≥500 student-attempts per subject |
| Official Exam Papers (Type 2 content) | Copyright clearance required; defer until legal framework is established |
| Email notification system | Beyond auth emails (password reset, welcome); no progress nudges in V1 |
| Admin sub-roles (creator vs. reviewer) | One admin in V1; add separation when team grows |
| Organisation / school / tutoring centre accounts | Nullable `organization_id` is in schema for future use; no feature built in V1 |
| Gamification (badges, streaks, leaderboards) | Nice-to-have; no evidence it's required for early adopters |
| Mobile app (iOS/Android) | PWA behaviour via Cloudflare Tunnel is sufficient for V1 |
| Bulk question import from CSV/spreadsheet | OCR pipeline handles bulk; CSV adds edge cases; defer |
| Student-to-student comparison / cohort analytics | Privacy implications; defer until legal review |

---

*End of Architecture Review — 2026-06-01*
*Next step: Address the 10 Required Decisions above before any code is written.*
*All decisions should be documented in `docs/OPEN_DECISIONS.md` as they are resolved.*
