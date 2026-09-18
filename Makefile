.PHONY: up down logs install db-upgrade db-downgrade seed test test-backend run-backend run-frontend build-frontend e2e

# ---- one-command deploy (single image, single port 3000) ----
up: ## docker compose: db (mssql 2022) + redis + the app
	docker compose up -d --build

down: ## stop the stack
	docker compose down

logs: ## follow app logs
	docker compose logs -f leadsynt

PY := python3
VENV := backend/.venv
BIN := $(VENV)/bin

install:
	cd backend && $(PY) -m venv .venv && .venv/bin/pip install -q -r requirements-dev.txt
	cd frontend && npm install

db-upgrade:
	cd backend && .venv/bin/alembic upgrade head

db-revision:
	cd backend && .venv/bin/alembic revision --autogenerate -m "$(m)"

seed:
	cd backend && .venv/bin/python ../scripts/seed_dev.py

test: test-backend

test-backend:
	cd backend && .venv/bin/pytest -q

run-backend:
	cd backend && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000

run-worker:
	cd backend && .venv/bin/celery -A app.workers.celery_app:celery worker --loglevel=info

run-frontend:
	cd frontend && npm run dev

build-frontend:
	cd frontend && npm run build

e2e:
	cd backend && .venv/bin/python ../tests/e2e/foundation_check.py
