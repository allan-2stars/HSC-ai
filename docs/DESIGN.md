# DESIGN.md

## Design Philosophy

The product should feel calm, trustworthy, and exam-focused. The interface should not feel like a game-first app, but it can use badges, streaks, and progress signals to motivate students.

## Primary Experience Principles

1. Exam clarity over visual decoration.
2. Parents need confidence and visibility.
3. Students need low-friction practice.
4. Administrators need efficient review tooling.
5. The UI must work well on iPad and desktop.

## Device Strategy

Primary devices:

- Desktop
- Laptop
- iPad
- Android tablet

Secondary devices:

- Mobile phones for login, account management, and reports only.

Exam mode should require a practical minimum screen width. Suggested minimum: 900px.

## Student UI

Student dashboard should show:

- Assigned exams
- Continue practice
- Recent results
- Recommended topics
- Streak/progress summary

Exam mode should include:

- Fixed timer
- Question area
- Answer area
- Question navigator
- Submit button
- Fullscreen state indicator

Avoid clutter during active exams.

## Parent UI

Parent dashboard should show:

- Student selector
- Subscription status
- Assigned exams
- Recent attempts
- Weak topics
- Progress trend
- Recommended next actions

Reports must be understandable without technical education jargon.

## Admin UI

Admin workspace should prioritise:

- Content creation
- OCR import queue
- Review queue
- Question bank search/filter
- Exam builder
- Publishing controls

Admin review screen should show:

- Original source page/image
- OCR text
- Structured extracted question
- Editable metadata
- Approval/rejection controls

## Visual Tone

Use:

- Clean typography
- Strong contrast
- Minimal distractions
- Clear status badges
- Accessible colors

Avoid:

- Toy-like visuals
- Excessive animation
- Dense tables without filters
- Mobile-only design assumptions
