# Open Decisions

These decisions are not required before documentation freeze, but should be revisited before implementation reaches the relevant milestone.

## 1. Product Name

Working name: HSC Exam Platform.

Need final commercial name later.

## 2. Payment Provider

Options:

- Stripe
- Paddle
- Other

Recommendation: Stripe unless there is a specific business reason not to.

## 3. AI Production Provider

Development may use DeepSeek.

Production provider requires legal/privacy review because the product involves children.

## 4. OCR Engine

Options:

- PaddleOCR
- Tesseract
- Google Document AI
- Azure Document Intelligence

Recommendation: start with PyMuPDF + PaddleOCR/Tesseract for MVP.

## 5. School/Teacher Accounts

Not V1, but data model should not block future support.

Future structure:

```text
School
  └── Teacher
       └── Class
            └── Students
```

## 6. Adaptive Learning Strategy

Recommendation:

- Start rule-based.
- Add AI-driven recommendations later.

## 7. Attempt History Limit

Current suggestion:

- Store up to 20 attempts per exam/student by default.
- Parent can manage/archive.

Need final retention policy.

## 8. Mobile Phone Policy

Recommendation:

- Allow account/report access.
- Discourage or block full exam mode on small screens.

Need final minimum width threshold.
