.PHONY: help setup dev backend frontend migrate test clean

help:  ## Show this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup:  ## Install backend + frontend deps and run migrations
	./scripts/setup.sh

dev:  ## Start backend (port 8000) and frontend (port 3000) in parallel
	./scripts/dev.sh

backend:  ## Start backend only
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000

frontend:  ## Start frontend only
	cd frontend && npm run dev

migrate:  ## Apply pending Alembic migrations
	cd backend && . .venv/bin/activate && alembic upgrade head

test:  ## Run backend tests
	cd backend && . .venv/bin/activate && pytest

clean:  ## Remove venv, node_modules, caches, and SQLite db
	rm -rf backend/.venv backend/__pycache__ backend/.pytest_cache
	rm -rf backend/nyx.db backend/uploads
	rm -rf frontend/node_modules frontend/.next
