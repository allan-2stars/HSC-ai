# Exam Engine Specification

## 1. Purpose

The exam engine provides a realistic timed exam experience for students and immutable attempt records for parents and analytics.

## 2. Exam Modes

### Practice Mode

- May allow immediate feedback depending on configuration.
- Useful for topic drills.

### Exam Mode

- Timed.
- No answer reveal before submission.
- Auto-submit on timeout.
- Attempts are immutable after submission.

### Writing Mode (Selective School)

- Timed writing prompt displayed to student.
- Student enters free-text response.
- No spell-check or grammar suggestions during exam.
- Auto-submit when time expires.
- Response stored as an immutable record after submission.
- AI-assisted feedback displayed after submission, with mandatory disclaimer.

V1 priority: Exam Mode and Writing Mode for OC and Selective.

## 3. Exam Session Flow

### Standard (MCQ/Structured) Exam

```text
Student selects exam
        ↓
Entitlement check
        ↓
Create attempt
        ↓
Enter fullscreen exam mode
        ↓
Student answers questions
        ↓
Submit or timeout
        ↓
Auto-mark
        ↓
Persist immutable result
        ↓
Show result and explanations
```

### Writing Exam

```text
Student selects writing exam
        ↓
Entitlement check
        ↓
Create attempt
        ↓
Enter fullscreen writing mode
        ↓
Display writing prompt
        ↓
Student writes response (free text)
        ↓
Submit or timeout
        ↓
Persist immutable writing response
        ↓
Trigger AI writing feedback (async)
        ↓
Show writing response and AI feedback with disclaimer
```

## 4. Timer Rules

- Timer starts when the attempt begins.
- Timer is shown in the top corner.
- Server stores the authoritative start time.
- Client timer is UI display only; backend validates timing on submission.
- Auto-submit when time expires.
- All timestamps stored as UTC.

## 5. Submission Rules

Students cannot:

- View answers before submission.
- Edit answers after submission.
- Edit writing responses after submission.
- Change score.
- Delete attempt history.

Retakes create new attempts.

## 6. Writing Feedback Rules

After a writing attempt is submitted:

- AI feedback is generated asynchronously and displayed when ready.
- Feedback covers: content, structure, vocabulary, and style.
- Feedback does not include an official mark or grade.
- The following disclaimer must appear on every screen displaying writing feedback:

  > "Writing feedback is educational guidance and does not represent official Selective School marking."

- Feedback is stored in the `WritingFeedback` table and linked to the writing response.
- Feedback does not modify the immutable attempt record.
- If AI feedback generation fails, the student sees: "Feedback is being prepared. Please check back shortly."

## 7. Attempt History

- All attempts are preserved.
- Default maximum stored attempts per exam per student: 20.
- Parent may archive according to policy.
- Student cannot delete attempts.
- Writing responses are retained as part of the attempt record.

## 8. Exam Security Mode

Exam mode creates a kiosk-like experience for deterrence purposes.

Features:

- Fullscreen request on exam start
- Fixed countdown timer
- Question navigator
- No right-click
- Disable text selection where practical
- Disable copy/paste keyboard events where practical
- Detect tab or window blur events
- Detect fullscreen exit
- Record all integrity events

Important limitation:

Browser-based controls are deterrence only, not absolute anti-cheating. The platform cannot prevent:

- External device use
- Screenshots outside browser control
- Another person helping

This limitation must be disclosed in the platform's terms of service. Exam mode is described as "Exam Simulation Mode" — it trains exam habits, not exam security.

## 9. Integrity Events

Record events for later parent and admin review:

- `fullscreen_exit`
- `tab_blur`
- `tab_focus`
- `copy_attempt`
- `paste_attempt`
- `right_click_attempt`

Integrity events are visible to the parent after submission. They are informational, not punitive.

## 10. Marking

V1 supports automatically marked questions:

- Multiple choice
- Single answer
- Short structured answer only if deterministic

Writing responses are not auto-marked. They receive AI-generated feedback only.

Future:

- Rubric-based scoring
- AI-assisted marking with explicit parent/admin disclosure

## 11. Review After Exam

After submission, student and parent can review:

- Question stem
- Student answer
- Correct answer
- Full explanation
- Topic tags
- Time spent per question

For writing exams, after submission the student and parent can review:

- Writing prompt
- Student writing response (immutable)
- AI feedback (with disclaimer)
- Word count
- Time spent

## 12. Device Restrictions

Exam mode should warn or block if the screen is too small.

Rule:

- Phone-size screens may browse and review results, but full exam mode requires tablet or desktop width.
- Minimum recommended width for exam mode: 768px.
- Writing mode requires sufficient text input area; minimum 768px strongly recommended.
