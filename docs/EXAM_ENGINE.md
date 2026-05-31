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

V1 priority: Exam Mode.

## 3. Exam Session Flow

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

## 4. Timer Rules

- Timer starts when the attempt begins.
- Timer is shown in the top corner.
- Server should store start time.
- Client timer is UI only; backend should validate timing.
- Auto-submit when time expires.

## 5. Submission Rules

Students cannot:

- View answers before submission.
- Edit answers after submission.
- Change score.
- Delete attempt history.

Retakes create new attempts.

## 6. Attempt History

- All attempts are preserved.
- Default maximum stored attempts per exam/student can be 20.
- Parent may archive/delete according to policy.
- Student cannot delete.

## 7. Exam Security Mode

Exam mode should create a kiosk-like experience.

Features:

- Fullscreen request
- Fixed timer
- Question navigator
- No right click
- Disable text selection where practical
- Disable copy/paste keyboard events where practical
- Detect tab/window blur
- Detect fullscreen exit
- Record integrity events

Important limitation:

Browser-based controls are deterrence only, not absolute anti-cheating.

## 8. Integrity Events

Record events such as:

- fullscreen_exit
- tab_blur
- tab_focus
- copy_attempt
- paste_attempt
- right_click_attempt

These events should be visible to parent/admin later if needed.

## 9. Marking

V1 should support automatically marked questions:

- Multiple choice
- Single answer
- Short structured answer only if deterministic

Future:

- Writing and long-form response marking
- Rubric-based scoring
- AI-assisted marking with admin/parent caution

## 10. Review After Exam

After submission, student and parent can review:

- Question stem
- Student answer
- Correct answer
- Full explanation
- Topic tags
- Time spent

## 11. Device Restrictions

Exam mode should warn or block if screen is too small.

Recommended rule:

- Phone-size screens can browse/review, but full exam mode requires tablet or desktop width.
