# Skill: Question Quality Review

Use this skill when implementing AI-assisted quality review for drafted questions before admin approval.

## Purpose

Assist the admin review process by flagging potential quality issues in AI-generated or OCR-imported questions before the admin makes a final decision.

## Important Limitation

AI quality review is an assistant to the admin, not a replacement.

The admin must always make the final approval or rejection decision. AI quality review output should be displayed as advisory suggestions only.

## What to Check

For every question submitted to quality review, check:

1. **Correctness** — Is the identified correct answer actually correct?
2. **Distractors** — Are the wrong options plausible but clearly incorrect?
3. **Ambiguity** — Could a reasonable student argue for more than one correct answer?
4. **Clarity** — Is the question stem clear and unambiguous?
5. **Age appropriateness** — Is the language appropriate for the target year level?
6. **Curriculum alignment** — Is the content consistent with the stated topic and year level?
7. **Explanation completeness** — Does the explanation fully justify the correct answer?
8. **Difficulty calibration** — Does the difficulty label seem consistent with the question?

## Input Requirements

The AI payload must contain:

- `stem` — question text
- `options` — array of answer options
- `correct_index` — index of the correct option
- `explanation` — the provided explanation
- `subject` — e.g., Mathematical Reasoning
- `topic` — specific topic
- `year_level` — 4, 5, or 6
- `exam_type` — OC or Selective
- `difficulty` — easy | medium | hard

The payload must NOT contain:

- Student data
- Attempt history
- Any personally identifying information

## Output Requirements

Return a structured review result:

```json
{
  "passes_review": true,
  "issues": [],
  "suggestions": ["Consider adding a note about why option B is incorrect"],
  "confidence": "high"
}
```

Or if issues are found:

```json
{
  "passes_review": false,
  "issues": [
    "The correct answer may be ambiguous — options A and C both could be argued",
    "The explanation does not address option B"
  ],
  "suggestions": [
    "Revise option C to make it more clearly incorrect",
    "Expand the explanation to address all distractors"
  ],
  "confidence": "medium"
}
```

## Display in Admin Review UI

Quality review results should be displayed as advisory flags in the admin question review screen.

- Green: AI review passed with no issues
- Amber: AI review passed with suggestions
- Red: AI review flagged issues — admin should review carefully

The admin can override any AI quality review result and approve or reject independently.

## Privacy

Do not include student data in quality review payloads. These are admin-facing requests only.
