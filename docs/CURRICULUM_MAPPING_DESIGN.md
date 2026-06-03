# Curriculum Mapping Design

## 1. Problem Statement

As HSC-ai scales content creation across OC, Selective, NAPLAN, and HSC exam types, the platform needs structured curriculum mapping to:

- Track which NSW curriculum outcomes are covered by existing questions
- Identify outcome gaps where content needs to be created
- Enable coverage reporting for admins to guide content seeding priorities
- Support the eventual content seeding dashboard (M4.7B)

Without formal mapping, admins have no systematic way to know whether the question bank provides adequate coverage for each exam type's curriculum requirements.

## 2. Architecture

```
CurriculumFramework     (e.g. "OC 2026", "Selective 2026", "NAPLAN 2026")
  └── CurriculumOutcome  (e.g. "OC-MATH-FRACTIONS", "SEL-TS-LOGIC")
        └── QuestionOutcomeMapping (question → outcome, with weight)
              └── Question (existing model)
```

Each framework groups outcomes for a specific exam type or subject area. Questions map to outcomes with an optional weight, supporting the case where a single question may assess multiple curriculum outcomes.

## 3. Database Design

### CurriculumFramework

| Field | Type | Notes |
|---|---|---|
| id | UUID string | PK |
| name | String(255) | e.g. "OC Mathematics 2026" |
| description | Text, nullable | |
| exam_type_id | FK → exam_types, nullable | Links framework to an exam type |
| version | String(50) | e.g. "2026" |
| is_active | Boolean | For soft-delete / archiving |
| created_at | DateTime | |
| updated_at | DateTime | |

### CurriculumOutcome

| Field | Type | Notes |
|---|---|---|
| id | UUID string | PK |
| framework_id | FK → curriculum_frameworks, CASCADE | |
| code | String(100), unique | e.g. "OC-MATH-FRACTIONS" |
| title | Text | e.g. "Fractions — Add and subtract with unlike denominators" |
| description | Text, nullable | |
| sort_order | Integer | Display ordering |
| created_at | DateTime | |

### QuestionOutcomeMapping

| Field | Type | Notes |
|---|---|---|
| id | UUID string | PK |
| question_id | FK → questions, CASCADE | |
| outcome_id | FK → curriculum_outcomes, CASCADE | |
| weight | Numeric(3,2), default 1.0 | Supports partial credit across outcomes |
| created_at | DateTime | |

Unique constraint on (question_id, outcome_id).

## 4. Entity Relationships

```
ExamType ──► CurriculumFramework (optional, nullable FK)
                │ 1:N
                ▼
          CurriculumOutcome
                │
                │ N:M via QuestionOutcomeMapping
                ▼
          Question (existing)
```

## 5. Scalability Considerations

- **Future HSC expansion**: HSC subjects are numerous (Mathematics Advanced, Extension 1/2, English, Physics, Chemistry, etc.). The framework/outcome model supports arbitrary numbers of frameworks without schema changes.
- **Year-level**: Frameworks can be scoped to year levels via naming convention or future `year_level` field.
- **NESA alignment**: Outcome codes can mirror NESA syllabus outcome codes for direct curriculum authority mapping.
- **Coverage queries**: The `QuestionOutcomeMapping` table supports efficient JOIN queries for coverage aggregation (COUNT by outcome, filtered by question status).

## 6. Coverage Calculation

Coverage for a framework is computed as:

- **Total outcomes**: All outcomes in the framework
- **Mapped outcomes**: Outcomes with ≥1 question mapping (any question status)
- **Covered outcomes**: Outcomes with ≥1 approved/published question
- **Coverage percentage**: (covered outcomes / total outcomes) × 100

Per-outcome coverage status thresholds:

| Questions | Status |
|---|---|
| 0 | RED — no content |
| 1–24 | AMBER — insufficient coverage |
| 25–99 | AMBER — moderate coverage |
| 100+ | GREEN — sufficient coverage |

## 7. Reporting Use Cases

Answers these questions:

1. Show all outcomes with fewer than 50 approved questions (targeted content seeding)
2. Show curriculum coverage for a specific exam type (e.g., OC Mathematics)
3. Show curriculum coverage for Selective Thinking Skills
4. Show unmapped questions (questions not linked to any outcome)
5. Show outcomes with zero questions (complete gaps)
6. Show coverage percentage per framework (dashboard summary)

## 8. API Design

Admin-only endpoints following existing `/admin` prefix pattern:

- `GET /curriculum/frameworks` — list all frameworks
- `POST /curriculum/frameworks` — create framework
- `GET /curriculum/frameworks/{id}` — framework detail with outcomes
- `GET /curriculum/outcomes` — list outcomes (filterable by framework_id)
- `POST /curriculum/outcomes` — create outcome
- `GET /curriculum/coverage/{framework_id}` — coverage report
- `POST /curriculum/question-mappings` — map question to outcome
- `DELETE /curriculum/question-mappings/{id}` — remove mapping

## 9. Future: M4.7B Content Seeding Dashboard

The models in M4.7A provide the data foundation on which the M4.7B dashboard will be built:

- Visual framework selector
- Coverage heatmap (green/amber/red per outcome)
- "Quick add" buttons to create questions targeting uncovered outcomes
- Bulk question-to-outcome mapping UI
- Import/export of outcome lists for content planning
