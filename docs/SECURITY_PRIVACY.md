# Security and Privacy Specification

## 1. Purpose

The platform handles children-related education data. Privacy, access control, data minimization, and copyright compliance are core requirements.

## 2. Family Account Model and Data Ownership

### Ownership Structure

The parent account owns all student data in V1.

- Parent is the account holder, subscriber, and data controller for all linked student accounts.
- Students are subordinate accounts with limited access scope.
- A student account cannot exist independently of a parent account.

### What Parents Can Do

- Create up to 3 student accounts.
- Set and reset student passwords.
- View all student attempt history and progress.
- Archive student attempt records according to retention policy.
- Close their account (which archives all linked student data).
- Request data export for all linked students.

### What Students Cannot Do

- Access billing or subscription information.
- Delete their own attempt history.
- Modify submitted answers or scores.
- Register without a parent account.
- Change their parent linkage.

### First Login Flow

Student accounts are created by the parent. On first login, the student must complete a password setup step before accessing any exams. Until this is completed, the student account is in a restricted state.

## 3. Role-Based Access

Roles:

- parent
- student
- admin

Access rules:

- Students can only access their own exams and results.
- Parents can access all data belonging to their linked student accounts.
- Admins can manage platform content and operational data, but not access individual student attempt data except for support purposes (logged access).
- Cross-account access is never permitted (a parent cannot view another parent's students).

## 4. Student Attempt Integrity

Submitted attempts are immutable.

Students cannot:

- Delete attempts
- Modify answers after submission
- Modify score

Parents may archive attempts according to product retention policy. Archiving does not delete the underlying data in V1; it only affects visibility.

## 5. AI Privacy Rules

### Core Principle

Student personal information must not be sent to external AI providers except where operationally necessary and documented.

### Allowed AI Payload Contents

The following data categories are permitted in AI provider requests:

- Prompt text (question or writing prompt)
- Student response text (writing content, answers)
- Rubric or marking criteria
- Year level (e.g., Year 5)
- Exam type (e.g., OC, Selective)
- Topic or subject label
- Question difficulty
- Generic performance pattern (e.g., percentage correct on fractions)
- Anonymized question IDs

### Prohibited AI Payload Contents

The following must never appear in AI provider request payloads:

- Student full name
- Student date of birth
- Parent name or identity
- Parent email address
- Billing or payment information
- Subscription plan details
- Contact details of any kind
- School name or location
- Any combination of fields that could re-identify the student

### AI Payload Audit

The `AIUsageLog` table includes a `payload_contained_student_data` boolean field to support periodic audits.

If any payload does contain student response data (e.g., writing assessment), the log entry must be flagged and the payload must be reviewed to confirm no personally identifying information is present.

### Writing Assessment

Writing assessment AI requests may contain the student's written response text. Before sending:

- Strip any student name or identifying information from the response if it appears.
- Include only: response text, writing prompt, rubric, year level, exam type.
- Do not include: student name, parent details, school information.

## 6. Content Copyright and Legal

### Copyright Risk

The platform may ingest content from OCR sources that are copyright-protected. Using commercial exam preparation content (such as past NSW Department of Education papers) without a valid licence is a legal risk.

### Content Ownership Classification

Every question in the system carries a `content_ownership` classification. This classification determines whether the question can be published to students.

| Classification | Description | Publishing Allowed |
|---|---|---|
| `original` | Written directly by a platform admin | Yes |
| `licensed` | Third-party content with a confirmed licence | Yes |
| `public_domain` | Confirmed as public domain | Yes |
| `approved_internal` | Internal draft promoted through full review | Yes |
| `user_provided_with_rights` | Submitted by a user with explicit rights declaration | Yes, with caution |
| `internal_draft` | Pending copyright review | No |
| `restricted_reference_only` | Copyright-restricted; admin reference only | No |

### OCR and Copyright

OCR is an ingestion tool. Scanning a copyrighted paper into the system does not grant any publishing rights.

- All OCR-imported content defaults to `internal_draft`.
- An admin must explicitly assign a publishable ownership classification during review.
- Assigning `original`, `licensed`, or `public_domain` to content that is not genuinely owned is a misuse of the platform and creates legal liability.
- Admins must confirm copyright status before assigning a publishable classification.

### What May Not Be Published Without Licence

- Official past OC test papers (NSW Department of Education)
- Official past Selective High School test papers (NSW Department of Education)
- Third-party workbooks or question banks without licence
- Copyrighted diagrams, charts, or images

### Recommended Safe Practices

- Write original questions modelled on exam style but not copied from specific papers.
- Obtain written licence agreements before importing third-party content.
- Link to official NSW DoE paper downloads rather than reproducing them.
- If in doubt, classify as `restricted_reference_only` and seek legal advice.

## 7. OCR Source File Privacy

Uploaded source files may contain copyrighted or sensitive content.

Store and track:

- Uploader admin ID
- Upload timestamp
- File checksum
- Source metadata

Restrict access to admin accounts only. Source files must never be accessible via public or student-accessible URLs.

## 8. Exam Security Limitations

Browser restrictions are deterrence only.

The platform can detect:

- Tab switch
- Fullscreen exit
- Right-click attempt
- Copy/paste attempt

The platform cannot fully prevent:

- External device use
- Screenshots outside browser control
- Another person helping

This limitation must be documented in the platform's terms of service. The exam engine provides exam simulation for learning purposes, not secure examination conditions.

## 9. Authentication

MVP must support:

- Email/password for parent and admin accounts
- Student PIN or password under parent account
- Secure password hashing (bcrypt or Argon2)
- Session expiration
- Role-aware login flows
- First-login password setup for student accounts

Future:

- Passkeys
- Social login for parent accounts
- MFA for admin accounts

## 10. Admin Security

Admin accounts should support:

- Audit logs for all content publishing actions
- All content review and approval actions attributed to the reviewing admin
- Role segmentation in future (content creator vs. content reviewer)

MVP may use same-role admin accounts. Code must not block future role separation.

## 11. Data Retention

Policy required for:

- Student attempt history (default: retained indefinitely while account is active)
- Deleted student accounts (archive, not hard delete, in V1)
- Parent account closure (archive all linked student data)
- OCR source files (retain for audit; admin may purge after review cycle)
- AI usage logs (retain for cost and audit tracking)

V1 must distinguish:

- Active records
- Archived records (hidden from normal views but retained)
- Deleted records (flagged, not physically removed, in V1)

## 12. Australian Privacy Act 1988

The platform is subject to the Australian Privacy Principles (APPs) under the Privacy Act 1988.

Key requirements relevant to this platform:

| APP | Requirement |
|---|---|
| APP 1 | Maintain and publish a privacy policy |
| APP 3 | Collect only information that is necessary |
| APP 5 | Notify individuals of data collection at point of collection |
| APP 6 | Use data only for the primary purpose it was collected for |
| APP 8 | Overseas disclosure must meet equivalent privacy standards |
| APP 11 | Protect personal information from misuse and loss |
| APP 12 | Individuals have the right to access their personal data |
| APP 13 | Individuals have the right to correct their personal data |

Note on APP 8: External AI providers that receive any personal data (even writing responses) must have data processing agreements that meet Australian Privacy Principles standards. Providers subject to foreign surveillance laws (such as data localisation requirements) require additional legal review before use with student data.
