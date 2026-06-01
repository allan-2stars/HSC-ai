# HSC AI Platform

NSW exam preparation for OC and Selective School — built for Raspberry Pi 5.

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, TypeScript, Tailwind CSS |
| Backend | FastAPI, Python 3.12 |
| Database | PostgreSQL 16 |
| Cache / Queue | Redis 7 |
| Storage | MinIO |
| Reverse proxy | Nginx |
| Deployment | Docker Compose, ARM64, Raspberry Pi 5 |

## Port Allocation

All ports use a dedicated range to avoid conflicts with other services on the Pi.

| Service | Host port | Container port | Notes |
|---|---|---|---|
| Web app (nginx) | **3090** | 80 | Primary entry point |
| MinIO API | **9190** | 9000 | S3-compatible storage API |
| MinIO Console | **9191** | 9001 | MinIO admin UI |
| PostgreSQL | — | 5432 | Internal Docker network only |
| Redis | — | 6379 | Internal Docker network only |
| Backend (FastAPI) | — | 8000 | Internal; accessed via nginx at `/api` |
| Frontend (Next.js) | — | 3000 | Internal; accessed via nginx at `/` |

## Quick Start

```bash
# 1. Copy environment file and edit values
cp .env.example .env

# 2. Start all services
make up

# 3. Visit the platform
open http://localhost:3090

# 4. API health check
open http://localhost:3090/api/health

# 5. API docs (Swagger UI)
open http://localhost:3090/api/docs

# 6. MinIO console (object storage admin)
open http://localhost:9191
```

PostgreSQL and Redis are internal Docker services and are not exposed to the host.

## Development Commands

```bash
make up        # Start all services (creates .env from .env.example if missing)
make down      # Stop all services
make logs      # Tail all service logs
make test      # Run all tests (backend + frontend)
make test-be   # Run backend tests (pytest)
make test-fe   # Run frontend tests (vitest)
make lint      # Lint backend + frontend
make format    # Format backend code (ruff)
```

## Project Structure

```
hsc-ai/
├── backend/          FastAPI application
│   ├── app/
│   │   ├── main.py         App entry point, health endpoint
│   │   └── core/
│   │       └── config.py   Environment configuration
│   └── tests/
├── frontend/         Next.js application
│   └── src/
│       ├── app/            Next.js App Router pages
│       └── components/     Shared UI components
├── nginx/            Reverse proxy configuration
├── docs/             Architecture and product documentation
├── skills/           AI skill definitions
├── docker-compose.yml
├── .env.example
└── Makefile
```

## Key Rules

- Parents own subscriptions and student data.
- Maximum 3 student accounts per parent.
- Students cannot delete attempts or modify submitted scores.
- Every published question must have a correct answer and full explanation.
- Admin review is mandatory before any OCR-imported or AI-generated question is published.
- AI features are Premium-only except limited trials.

## Documentation

| Document | Purpose |
|---|---|
| [PRD](docs/PRD.md) | Product requirements |
| [Architecture](docs/ARCHITECTURE.md) | System architecture |
| [Data Model](docs/DATA_MODEL.md) | Database schema |
| [Question Bank](docs/QUESTION_BANK.md) | Content hierarchy |
| [Content Strategy](docs/CONTENT_STRATEGY.md) | Content governance |
| [Exam Engine](docs/EXAM_ENGINE.md) | Exam session behaviour |
| [Security & Privacy](docs/SECURITY_PRIVACY.md) | Privacy and access control |
| [Roadmap](docs/ROADMAP.md) | Milestone plan |

## Current Milestone

**Milestone 0 — Project Bootstrap** ✓

Health endpoint: `GET http://localhost:3090/api/health`

Next: Milestone 1 — Auth foundation and question bank.
