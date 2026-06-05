# M4.8 Content Seeding Pilot

## 1. Purpose

Validate the full HSC-ai content pipeline end-to-end using a real content pack targeting OC Mathematics. This ensures all pipeline stages — generation, review, publication, exam creation, and assignment — work together correctly.

## 2. Target

- **Exam Type**: Opportunity Class (OC)
- **Subject**: Mathematics
- **Framework**: OC Mathematics 2026
- **Total Questions**: 100 published
- **Outcomes**: 5 curriculum outcomes, 20 questions each

## 3. Outcomes Covered

| Outcome Code | Title | Published Qs |
|---|---|---|
| OC-MATH-FRACTIONS | Fractions — equivalence, addition, subtraction, multiplication | 20 |
| OC-MATH-DECIMALS | Decimals — place value, operations, conversion | 20 |
| OC-MATH-PERCENTAGES | Percentages — calculate, compare, apply discounts | 20 |
| OC-MATH-PATTERNS | Patterns & Algebra — sequences, rules, expressions | 20 |
| OC-MATH-GEOMETRY | Geometry — angles, 2D/3D shapes, measurement | 20 |

## 4. Difficulty Distribution

- Easy: 30%
- Medium: 50%
- Hard: 20%

## 5. Pipeline Stages Exercised

```
1. Taxonomy creation (subjects, exam types, topics, skill tags)
2. Curriculum framework + outcome creation
3. AI question generation (mock provider, 20 per outcome)
4. Validation (per-question MCQ structure checks)
5. Lifecycle: draft → review → approved → published
6. Outcome auto-mapping
7. Sample exam creation (20 questions from published pool)
8. Parent assignment creation (linked to seed student)
9. Coverage snapshot (before/after comparison)
```

## 6. How to Run

```bash
make seed-dev       # First, create the base seed data (users, taxonomy)
make seed-pilot     # Then run the content seeding pilot
```

Or directly:
```bash
docker compose exec backend python -m app.seed
docker compose exec backend python -m app.pilot_seed
```

## 7. Verification Checklist

After running `make seed-pilot`, verify:

- [ ] `http://localhost:3090/admin/curriculum` — coverage dashboard shows 5 outcomes with published questions
- [ ] `http://localhost:3090/admin/content/review?source_type=ai` — AI-generated questions visible
- [ ] `http://localhost:3090/exams` — Sample exam visible to students
- [ ] Student can start and complete the exam
- [ ] Parent can see student progress

### Test Accounts

| Role | Email | Password |
|---|---|---|
| Admin | `admin@hsc.local` | `admin123` |
| Parent | `parent@hsc.local` | `parent123` |
| Student | `seed01@students.hscai.internal` | `student123` |

## 8. Results Snapshot

The seed script outputs per-outcome counts and coverage before/after:

```
Per-Outcome:
  OC-MATH-FRACTIONS:     gen=20 saved=20 published=20
  OC-MATH-DECIMALS:      gen=20 saved=20 published=20
  OC-MATH-PERCENTAGES:   gen=20 saved=20 published=20
  OC-MATH-PATTERNS:      gen=20 saved=20 published=20
  OC-MATH-GEOMETRY:      gen=20 saved=20 published=20

Totals: 100 generated, 100 saved, 0 rejected, 100 published

Coverage:
  OC-MATH-FRACTIONS:     0 → 20 published
  OC-MATH-DECIMALS:      0 → 20 published
  OC-MATH-PERCENTAGES:   0 → 20 published
  OC-MATH-PATTERNS:      0 → 20 published
  OC-MATH-GEOMETRY:      0 → 20 published
```

## 9. Idempotency

The script is idempotent — all `_ensure_*` functions check for existing data before creating. Running `make seed-pilot` multiple times does not duplicate content.

## 10. Future Pilots

This pattern can be reused for:
- OC Thinking Skills (100 questions)
- Selective Mathematics (100 questions)
- NAPLAN Numeracy (100 questions)
- HSC Mathematics Advanced (200 questions)
