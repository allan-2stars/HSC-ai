# Content Quality Framework

## 1. Purpose

The Content Quality Framework provides a structured scoring rubric for evaluating all content in the HSC-ai platform. It enables objective comparison across content sources (manual, imported, OCR, AI) and AI providers (OpenAI, Claude, DeepSeek, Ollama), and identifies questions that should be regenerated or revised.

## 2. Scoring Rubric

Every review scores a question across five dimensions:

| Dimension | Scale | Description |
|---|---|---|
| Correctness | 1-5 | Is the answer objectively correct? 5 = demonstrably correct, 1 = factually wrong |
| Outcome Alignment | 1-5 | Does the question genuinely assess the curriculum outcome? 5 = perfectly aligned, 1 = unrelated |
| Difficulty Accuracy | 1-5 | Does the assigned difficulty match the question? 5 = perfectly calibrated, 1 = wildly mismatched |
| Explanation Quality | 1-5 | Would the explanation help a student learn? 5 = comprehensive and clear, 1 = useless or missing |
| Overall Quality | 1-5 | Would this question be acceptable in a paid product? 5 = excellent, 1 = unacceptable |

## 3. Review Process

1. **Admin opens Content Review** (`/admin/content/review`)
2. **Selects a question** for quality review
3. **Scores** on all five dimensions (1-5)
4. **Adds notes** for context
5. **Saves** — review is stored in `question_quality_reviews`

Multiple reviews per question are supported. The dashboard averages all reviews.

## 4. Analytics Dashboard

Available at `/admin/content/quality`:

- **Summary cards**: Total reviews, unique questions reviewed, average overall score, needs revision count
- **Source comparison**: Average quality by content source (manual, ai, ocr, imported)
- **Provider performance**: Saved/rejected counts, rejection rate, publication rate per AI provider
- **Outcome quality**: Per-outcome average scores, questions needing regeneration
- **Regeneration candidates**: Questions with overall_score < 3, flagged for revision

## 5. Source Benchmarking

Content sources are compared on average quality:

```
manual       → avg 4.2
ai           → avg 3.8
ocr          → avg 3.1
imported     → avg 3.5
```

AI providers are compared on publication rate:

```
Provider A   → 95% published
Provider B   → 80% published
```

These metrics identify which content pipelines need process improvements.

## 6. Regeneration Workflow

Questions flagged as "Needs Regeneration" (overall_score < 3) should:

1. Be reviewed by a second admin to confirm the low score
2. If confirmed, the question should be archived
3. A new AI generation should target the same curriculum outcome
4. The new question goes through the standard review → publish workflow

This ensures continuous improvement of the question bank.

## 7. APIs

| Method | Path | Purpose |
|---|---|---|
| POST | `/admin/content/quality-review` | Create a quality review |
| GET | `/admin/content/quality-reviews?question_id=` | List reviews |
| GET | `/admin/content/quality-dashboard` | Aggregated quality dashboard |
| GET | `/admin/content/quality-by-provider` | Source + provider comparison |
| GET | `/admin/content/quality-by-outcome` | Per-outcome quality metrics |
| GET | `/admin/content/quality-regeneration-candidates` | Questions needing rework |

## 8. Integration with Review Queue

The content review page (`/admin/content/review`) should eventually include inline quality scoring. For M4.9, scoring is available via the quality API and dashboard but not yet embedded in the review queue UI.

## 9. Best Practices

1. **Review before publishing** — score questions during the review phase, not after publication
2. **Second reviewer** — where possible, have a different admin review than the one who created/approved
3. **Trend watch** — monitor `needs_regeneration` counts rising, which indicates process degradation
4. **Source benchmarking** — use source comparison to identify which content pipeline needs investment
5. **Outcome gaps** — outcomes with consistently low average scores may need better prompting or manual content creation
