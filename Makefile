BACKEND_VENV := backend/.venv
BACKEND_PY   := $(BACKEND_VENV)/bin/python
BACKEND_PIP  := $(BACKEND_VENV)/bin/pip
BACKEND_PYTEST := $(BACKEND_VENV)/bin/pytest
BACKEND_RUFF := $(BACKEND_VENV)/bin/ruff

.PHONY: help up down logs test test-be test-fe lint format migrate migrate-new seed seed-dev shell-be create-test-db install-be

help:
	@echo ""
	@echo "HSC AI Platform — Development Commands"
	@echo "───────────────────────────────────────"
	@echo "  make up        Start all services"
	@echo "  make down      Stop all services"
	@echo "  make logs      Tail all service logs"
	@echo "  make test      Run backend + frontend tests"
	@echo "  make test-be   Run backend tests (pytest)"
	@echo "  make test-fe   Run frontend tests (vitest)"
	@echo "  make lint      Lint backend + frontend"
	@echo "  make format    Format backend code"
	@echo "  make migrate         Apply pending migrations"
	@echo "  make migrate-new     Generate new migration (name=<message>)"
	@echo "  make seed            Seed subscription plans"
	@echo "  make seed            Seed subscription plans
  make seed-dev        Full development seed (users, questions, exams)
  make create-test-db  Create hscai_test database"
	@echo "  make shell-be        Open shell in backend container"
	@echo ""

# ── Docker Compose ────────────────────────────────────────────────

up:
	@cp -n .env.example .env 2>/dev/null && echo "Created .env from .env.example" || true
	docker compose up -d
	@echo "Services started. Web: http://localhost:3090  API: http://localhost:3090/api/health"

down:
	docker compose down

logs:
	docker compose logs -f

shell-be:
	docker compose exec backend bash

# ── Backend tests (runs inside Docker container) ──────────────────

test-be:
	docker compose exec backend python -m pytest -v

# ── Frontend tests (runs locally via npm) ─────────────────────────

test-fe:
	cd frontend && npm install --silent && npm test

# ── Combined test target ──────────────────────────────────────────

test: test-be test-fe

# ── Linting ───────────────────────────────────────────────────────

$(BACKEND_VENV):
	python3 -m venv $(BACKEND_VENV)

.PHONY: install-be
install-be: $(BACKEND_VENV)
	$(BACKEND_PIP) install --quiet -r backend/requirements.txt -r backend/requirements-dev.txt

lint: install-be
	$(BACKEND_RUFF) check backend/
	cd frontend && npm install --silent && npm run lint

# ── Formatting ────────────────────────────────────────────────────

format: install-be
	$(BACKEND_RUFF) format backend/

# ── Migrations ───────────────────────────────────────────────────

migrate:
	docker compose exec backend alembic upgrade head

migrate-new:
	docker compose exec backend alembic revision --autogenerate -m "$(name)"

seed:
	docker compose exec backend python -c "import asyncio; from app.core.database import SessionLocal; from app.services.seed_service import seed_plans; asyncio.run(SessionLocal().__aenter__().send(None) or seed_plans(None))"
	@echo "Note: run 'make seed' or call seed_plans() from a Python REPL for now"

seed-dev:
	docker compose exec backend python -m app.seed

create-test-db:
	docker compose exec postgres createdb -U hscai hscai_test 2>/dev/null || echo "Test database already exists"
