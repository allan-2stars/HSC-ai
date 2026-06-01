# Skill: NSW Selective Question Generation

Use this skill when generating AI-drafted questions for the NSW Selective High School Placement Test.

## Scope

Target exam: NSW Selective High School Placement Test
Target students: Year 6 (applying for Year 7 Selective entry)
Question formats: Multiple choice (MCQ) and writing prompts
Marking: Auto-marked for MCQ; AI-assisted feedback only for writing

## Subject Areas

Generate questions for:

- Mathematical Reasoning — number, algebra, measurement, space and geometry, data
- Thinking Skills — verbal reasoning, non-verbal reasoning, abstract reasoning, logical sequences
- Reading — extended passage comprehension, inference, vocabulary, text analysis
- Writing — writing prompts (narrative, persuasive, informative, imaginative)

## Quality Standards for MCQ

Every generated MCQ question must meet:

- Age-appropriate language for Year 6 students (approximately 11–12 years old)
- 4 answer options (A, B, C, D)
- One unambiguous correct answer
- A full explanation of why the correct answer is correct
- Topic tag matching one of the supported Selective subject areas
- Difficulty rating: easy | medium | hard

## Quality Standards for Writing Prompts

Every generated writing prompt must:

- Be appropriate for Year 6 students
- Clearly state the prompt type: narrative | persuasive | informative | imaginative
- Be unambiguous — students should understand what is being asked
- Be culturally inclusive
- Not reproduce specific prompts from official NSW Selective past papers
- Include a suggested word limit (optional)
- Include suggested time limit in seconds (optional)

## What to Avoid

- Questions that require knowledge beyond Year 6 NSW curriculum
- Ambiguous MCQ answers
- Culturally insensitive content
- Writing prompts with inherently controversial political content inappropriate for the age group
- Questions that reproduce specific content from official NSW Selective past papers

## MCQ Output Format

```json
{
  "stem": "Question text here",
  "options": ["Option A", "Option B", "Option C", "Option D"],
  "correct_index": 2,
  "explanation": "Full explanation of the correct answer",
  "subject": "Mathematical Reasoning",
  "topic": "Algebra",
  "exam_type": "Selective",
  "year_level": 6,
  "difficulty": "hard"
}
```

## Writing Prompt Output Format

```json
{
  "prompt_text": "Write a persuasive speech about why ...",
  "prompt_type": "persuasive",
  "subject": "Writing",
  "exam_type": "Selective",
  "year_level": 6,
  "word_limit": 400,
  "time_limit_seconds": 1800
}
```

## Writing Feedback Disclaimer

Any system that uses this skill to assess writing responses must display the following disclaimer:

> "Writing feedback is educational guidance and does not represent official Selective School marking."

## Privacy

Do not include in the AI payload:

- Student names or identifiers
- Parent information
- Any personally identifying information

For writing assessment payloads, include only: response text, prompt, rubric, year level, exam type.
