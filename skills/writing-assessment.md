# Skill: Writing Assessment

Use this skill when implementing AI-assisted writing feedback for student writing responses.

## Purpose

Provide structured, educational feedback on student writing responses for the Selective School writing component.

This skill does not produce official marking. It produces guidance to help students improve.

## Mandatory Disclaimer

Every surface that displays writing feedback generated through this skill must show:

> "Writing feedback is educational guidance and does not represent official Selective School marking."

This disclaimer is non-negotiable and cannot be removed or hidden.

## Scope

- Exam type: Selective (only in V1)
- Year level: 6
- Supported prompt types: narrative, persuasive, informative, imaginative

## Input Requirements

The AI payload must contain:

- `prompt_text` — the writing prompt shown to the student
- `prompt_type` — narrative | persuasive | informative | imaginative
- `response_text` — the student's written response
- `year_level` — 6
- `exam_type` — Selective
- `rubric` (optional) — structured scoring criteria if available

The payload must NOT contain:

- Student name
- Student date of birth
- Parent information
- School name
- Any personally identifying information

If the student's response contains their name, it should be stripped or masked before sending.

## Output Requirements

The AI must return structured feedback covering:

- **Content and ideas** — relevance to prompt, depth, originality
- **Structure and organisation** — introduction, body, conclusion, paragraphing
- **Language and vocabulary** — word choice, variety, age-appropriateness
- **Grammar and mechanics** — sentence structure, punctuation, spelling
- **Overall guidance** — 2–3 specific, actionable suggestions for improvement

The AI must NOT:

- Assign a numerical mark or grade
- Make statements like "This would score X/Y"
- Compare the student to other students
- Make discouraging or demotivating statements

## Storage

Writing feedback is stored in the `WritingFeedback` table.

Fields to populate:

- `writing_attempt_response_id`
- `ai_provider`
- `feedback_text`
- `criteria_scores_json` (if rubric-based scoring was returned)
- `generated_at`
- `model_version` (optional)

Writing feedback is NOT part of the immutable attempt record. It is supplementary and can be regenerated if needed.

## Error Handling

If the AI provider fails to generate feedback:

- Store the failure in the `WritingFeedback` record with an error state
- Display to the student: "Feedback is being prepared. Please check back shortly."
- Do not display a raw API error to the student

## Privacy Audit

All writing assessment requests must be logged in `AIUsageLog` with:

- `payload_contained_student_data = true`
- `feature = "writing_assessment"`
