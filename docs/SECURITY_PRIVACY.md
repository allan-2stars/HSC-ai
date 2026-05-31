# Security and Privacy Specification

## 1. Purpose

The platform handles children-related education data. Privacy, access control, and data minimization are core requirements.

## 2. User Data Ownership

Parent account owns student data in V1.

Students are linked to parents and inherit subscription access.

## 3. Role-Based Access

Roles:

- parent
- student
- admin

Access rules:

- Students can only access their own exams/results.
- Parents can access linked student data.
- Admins can manage platform content and operational data.

## 4. Student Attempt Integrity

Submitted attempts are immutable.

Students cannot:

- Delete attempts
- Modify answers after submission
- Modify score

Parents may archive/delete according to product policy.

## 5. AI Privacy

AI requests should minimize personal data.

Avoid sending:

- student name
- parent name
- email address
- payment information
- unnecessary identifiers

Use IDs or anonymized summaries where possible.

## 6. OCR Privacy

Uploaded source files may contain copyrighted or sensitive content.

Store:

- uploader
- upload time
- checksum
- source metadata

Restrict access to admins.

## 7. Exam Security Limitations

Browser restrictions are deterrence only.

The platform can detect:

- tab switch
- fullscreen exit
- right-click attempt
- copy/paste attempt

The platform cannot fully prevent:

- external device use
- screenshots outside browser control
- another person helping

## 8. Authentication

MVP should support:

- Email/password
- Secure password hashing
- Session expiration
- Role-aware login

Future:

- Passkeys
- Social login
- MFA for admins

## 9. Admin Security

Admin accounts should eventually support:

- MFA
- Audit logs
- Role segmentation
- Content publishing audit trail

MVP may use simple same-role admin accounts, but code should not prevent future role separation.

## 10. Data Retention

Need policy for:

- Student attempt history
- Deleted student accounts
- Parent account closure
- OCR source files
- AI logs

V1 should at least distinguish active, archived, and deleted records.
