# PRD: HSC Exam Platform

## 1. Overview

The HSC Exam Platform is a NSW-focused online exam preparation product. It starts with OC and Selective School preparation and later expands to NAPLAN and HSC.

The platform helps students practise exam-style questions in a timed, structured environment. Parents can track progress, assign work, review answers, and manage subscriptions. Administrators can create, import, review, and publish exam content.

## 2. Product Vision

Create a trusted NSW exam practice platform that combines:

- Timed exam simulation
- Structured question bank
- Parent progress dashboards
- Full answer explanations
- OCR-powered content ingestion
- AI-assisted question generation and learning recommendations

## 3. Target Users

### 3.1 Students

Students take practice exams, review results, and follow recommended practice.

### 3.2 Parents

Parents are the primary paying customers. They manage student accounts, subscriptions, assigned exams, and progress review.

### 3.3 Administrators

Administrators manage content, OCR imports, AI-generated questions, subscriptions, and platform announcements.

## 4. Launch Scope

### V1

- OC preparation
- Selective School preparation

### V2

- NAPLAN

### V3

- HSC

## 5. Core Value Proposition

For parents:

- Know what the child practised.
- Know what the child got wrong.
- Know which topics need improvement.
- See measurable progress over time.

For students:

- Practise exam-style questions.
- Experience realistic timer pressure.
- Review full explanations.
- Improve by topic and skill.

For administrators:

- Build and maintain a high-quality question bank.
- Import exam material using OCR.
- Generate draft questions using AI.
- Control publishing quality through review workflows.

## 6. User Roles

### Parent

Can:

- Register and log in.
- Purchase subscriptions.
- Create up to 3 student accounts.
- Assign exams to students.
- View student progress.
- Review student answers.
- Manage attempt history according to policy.

### Student

Can:

- Log in under linked parent account.
- Take assigned or available exams.
- Review completed attempts.
- See progress and recommendations.

Cannot:

- Delete attempt records.
- Change submitted answers.
- Change scores.
- View answers before submitting an exam.

### Administrator

Can:

- Manage users and subscriptions.
- Create subjects, topics, questions, and exams.
- Upload OCR sources.
- Generate draft questions using AI.
- Review, approve, publish, archive, or reject content.
- Publish announcements/news.

MVP admin model: all admin accounts have the same access level.

## 7. Subscription Model

Subscription options:

- All Access
- Subject package
- Exam Type package

Billing periods:

- Monthly
- Annual

AI features:

- Premium only.
- Free/trial users may receive limited AI usage.

## 8. Question Requirements

Every published question must include:

- Question stem
- Answer options or expected response format
- Correct answer
- Full explanation
- Subject
- Exam type
- Topic/skill tags
- Difficulty
- Source/provenance metadata

## 9. Content Sources

Questions can come from:

1. Manual admin entry
2. OCR import from PDF/image/photo
3. AI-generated draft content

All sources must pass admin review before publishing.

## 10. Exam Experience

Exam mode must feel close to a real online exam:

- Fullscreen mode
- Timer in top corner
- Question navigator
- Auto-submit on timeout
- No answer checking during exam
- No score editing after submission
- Integrity event logging

## 11. Analytics

V1 analytics:

- Score per attempt
- Correct/incorrect questions
- Topic-level weakness summary
- Time spent
- Attempt history

Future analytics:

- Readiness score
- Adaptive recommendations
- AI tutor explanations
- Parent weekly digest

## 12. Success Metrics

Product metrics:

- Parent sign-up rate
- Trial-to-paid conversion
- Student weekly active usage
- Exams completed per student
- Retention after 30 days

Learning metrics:

- Accuracy improvement by topic
- Attempt completion rate
- Repeated weakness reduction

Operational metrics:

- OCR import success rate
- Review queue throughput
- Question publishing quality
