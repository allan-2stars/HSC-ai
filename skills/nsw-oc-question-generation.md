# Skill: NSW OC Question Generation

Use this skill when generating AI-drafted questions for the NSW Opportunity Class (OC) Placement Test.

## Scope

Target exam: NSW OC Placement Test
Target students: Year 4 (applying for Year 5 OC entry)
Question format: Multiple choice only
Marking: Auto-marked (no writing component in OC)

## Subject Areas

Generate questions for:

- Mathematical Reasoning — number, operations, fractions, measurement, space and geometry, patterns
- Thinking Skills — verbal reasoning, non-verbal reasoning, logical patterns, sequences
- Reading — comprehension, inference, vocabulary in context, passage-based questions

## Quality Standards

Every generated question must meet:

- Age-appropriate language for Year 4 students (approximately 9–10 years old)
- 4 answer options (A, B, C, D)
- One unambiguous correct answer
- A full explanation of why the correct answer is correct
- A brief note on why common wrong answers are wrong (if practical)
- Topic tag matching one of the supported OC subject areas
- Difficulty rating: easy | medium | hard

## What to Avoid

- Questions that require knowledge beyond Year 4 NSW curriculum
- Ambiguous correct answers
- Culturally insensitive content
- Australian-specific content that may disadvantage non-English-speaking students unfairly
- Questions that reproduce specific content from official NSW OC past papers

## Prompt Template Guidance

When constructing a generation prompt, include:

- Subject area
- Topic
- Year level: 4
- Exam type: OC
- Desired difficulty
- Number of questions
- Format: MCQ with 4 options, correct answer, full explanation

## Output Format

```json
{
  "stem": "Question text here",
  "options": ["Option A", "Option B", "Option C", "Option D"],
  "correct_index": 0,
  "explanation": "Full explanation of the correct answer",
  "subject": "Mathematical Reasoning",
  "topic": "Fractions",
  "exam_type": "OC",
  "year_level": 4,
  "difficulty": "medium"
}
```

## Privacy

Do not include in the AI payload:

- Student names or identifiers
- Parent information
- Any personally identifying information
