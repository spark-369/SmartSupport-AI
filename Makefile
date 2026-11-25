# SmartSupport AI — developer workflows

SHELL := /bin/bash
BACKEND := backend
FRONTEND := frontend
PY := $(BACKEND)/venv/bin

.PHONY: help install migrate seed api worker frontend test build clean

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## install backend + frontend dependencies
	cd $(BACKEND) && python3 -m venv venv && venv/bin/pip install -q -r requirements.txt
	cd $(FRONTEND) && npm install

migrate: ## apply alembic migrations (dev DB)
	cd $(BACKEND) && $(PY)/alembic upgrade head

seed: ## seed admin + demo product + sample manual (inline ingestion)
	cd $(BACKEND) && $(PY)/python scripts/seed.py

api: ## run the FastAPI dev server
	cd $(BACKEND) && $(PY)/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

worker: ## run the Celery worker
	cd $(BACKEND) && $(PY)/celery -A app.workers.celery_app.celery_app worker --loglevel=INFO

frontend: ## run the Vite dev server
	cd $(FRONTEND) && npm run dev

test: ## run the backend pytest suite
	cd $(BACKEND) && $(PY)/python -m pytest -q

build: ## type-checked production build of the frontend
	cd $(FRONTEND) && npm run build

clean: ## remove build artifacts and caches
	rm -rf $(FRONTEND)/dist $(FRONTEND)/node_modules/.tmp
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
