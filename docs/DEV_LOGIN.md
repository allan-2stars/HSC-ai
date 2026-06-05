# Development Login Credentials

After running the seed command:

```
make seed-dev
# or
docker compose exec backend python -m app.seed
```

## Test Accounts

| Role | Email | Password | Notes |
|---|---|---|---|
| Admin | `admin@hsc.local` | `admin123` | Full backend admin access |
| Admin 2 | `ai.signpega@gmail.com` | `Admin123!` | Full backend admin access |
| Parent | `parent@hsc.local` | `parent123` | Has one student linked |
| Student | `seed01@students.hscai.internal` | `student123` | Linked to Seed Parent, Year 5 |

## Role Home Pages

After login, users are redirected based on role:

| Role | Home Page |
|---|---|
| Parent | `http://localhost:3090/parent` |
| Student | `http://localhost:3090/me` |
| Admin | `http://localhost:3090/admin/curriculum` |

| Page | URL | Auth |
|---|---|---|
| Landing | `http://localhost:3090/` | None |
| Login | `http://localhost:3090/login` | None |
| Register | `http://localhost:3090/register` | None |
| My Account | `http://localhost:3090/me` | Any |
| Parent Dashboard | `http://localhost:3090/parent` | Parent |
| Manage Students | `http://localhost:3090/students` | Parent |
| Manage Assignments | `http://localhost:3090/parent/assignments` | Parent |
| Student Analytics | `http://localhost:3090/parent/students/<id>` | Parent |
| Available Exams | `http://localhost:3090/exams` | Student |
| My Assignments | `http://localhost:3090/me/assignments` | Student |
| My Progress | `http://localhost:3090/me/progress` | Student |
| Curriculum Dashboard | `http://localhost:3090/admin/curriculum` | Admin |

## End-to-End Test Flow

1. Open `http://localhost:3090/` and click **Sign In**
2. Login as **Student** (`seed01@students.hscai.internal` / `student123`)
3. Navigate to **My Assignments** — see the seeded assignment
4. Click **Start Exam** to begin the seed exam
5. Answer questions and click **Submit Exam**
6. View your result
7. Sign out and login as **Parent** (`parent@hsc.local` / `parent123`)
8. Navigate to **View Dashboard** — see student analytics
9. Navigate to **Manage Assignments** — see assignment status
10. Sign out and login as **Admin** (`admin@hsc.local` / `admin123`)
11. Navigate to **Curriculum Dashboard** — see coverage data

## Seeded Content

- 2 exam types (OC, Selective)
- 3 subjects with topics and skill tags
- 1 curriculum framework with 6 outcomes
- 12 published MCQ questions across Mathematics, English, Thinking Skills
- 1 question pool (OC Maths Practice Pool)
- 1 exam template with 12 questions → 1 published exam instance
- 1 parent assignment for the seed student
