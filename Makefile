BACKEND_VENV := backend/.venv
BACKEND_PY   := $(BACKEND_VENV)/bin/python
BACKEND_PIP  := $(BACKEND_VENV)/bin/pip
BACKEND_PYTEST := $(BACKEND_VENV)/bin/pytest
BACKEND_RUFF := $(BACKEND_VENV)/bin/ruff

.PHONY: help up down logs test test-be test-fe lint format migrate shell-be

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
	@echo "  make migrate   Run database migrations (Milestone 1+)"
	@echo "  make shell-be  Open shell in backend container"
	@echo ""

# ── Docker Compose ────────────────────────────────────────────────

up:
	@cp -n .env.example .env 2>/dev/null && echo "Created .env from .env.example" || true
	docker compose up -d
	@echo "Services started. Frontend: http://localhost  Backend: http://localhost/api/health"

down:
	docker compose down

logs:
	docker compose logs -f

shell-be:
	docker compose exec backend bash

# ── Backend tests (runs locally in venv for speed) ────────────────

$(BACKEND_VENV):
	python3 -m venv $(BACKEND_VENV)

.PHONY: install-be
install-be: $(BACKEND_VENV)
	$(BACKEND_PIP) install --quiet -r backend/requirements.txt -r backend/requirements-dev.txt

test-be: install-be
	$(BACKEND_PYTEST) backend/tests/ -v

# ── Frontend tests (runs locally via npm) ─────────────────────────

test-fe:
	cd frontend && npm install --silent && npm test

# ── Combined test target ──────────────────────────────────────────

test: test-be test-fe

# ── Linting ───────────────────────────────────────────────────────

lint: install-be
	$(BACKEND_RUFF) check backend/
	cd frontend && npm install --silent && npm run lint

# ── Formatting ────────────────────────────────────────────────────

format: install-be
	$(BACKEND_RUFF) format backend/

# ── Migrations (wired up in Milestone 1) ─────────────────────────

migrate:
	@echo "Migrations are configured in Milestone 1. See backend/alembic/ (future)."
