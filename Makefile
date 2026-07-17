# HyerEnrichment — common local-dev targets
# Free Docker stack: api, worker, redis, postgres, social-analyzer, google-maps-scraper

.PHONY: help setup up down test smoke smoke-prod boundary-checks migrate integration-e2e e2e-full-path

.DEFAULT_GOAL := help

BACKEND_DIR := backend
DOCKER_DIR := backend/docker
FREE_STACK := api worker redis postgres social-analyzer google-maps-scraper

help: ## List available targets
	@echo "Targets:"
	@echo "  setup    Copy backend/.env if missing; create backend/.venv; pip install -e .[dev] + requests"
	@echo "  up       Start free Docker stack detached (runs migrate job before api/worker)"
	@echo "  down     Stop Docker Compose stack (backend/docker)"
	@echo "  test     Run pytest in backend"
	@echo "  smoke    Run backend/scripts/smoke_test.py (SMOKE_SKIP_ASYNC=1 for sync-only)"
	@echo "  smoke-prod  Smoke against BASE_URL (requires BASE_URL + API_TOKEN)"
	@echo "  boundary-checks  Run compliance/rate-limit boundary pytest bundle"
	@echo "  migrate  Run Alembic upgrade head in backend"
	@echo "  integration-e2e  Start backend stack and run frontend Playwright integration tests"
	@echo "  e2e-full-path     Run backend full-path E2E harness (CI mode)"
	@echo "  help     Show this help"

setup: ## Env file + editable backend install (venv; avoids PEP 668)
	@if [ ! -f $(BACKEND_DIR)/.env ]; then \
		cp $(BACKEND_DIR)/.env.example $(BACKEND_DIR)/.env; \
		echo "Created $(BACKEND_DIR)/.env from .env.example"; \
	else \
		echo "$(BACKEND_DIR)/.env already exists - skipping copy"; \
	fi
	@if [ ! -d $(BACKEND_DIR)/.venv ]; then \
		python3 -m venv $(BACKEND_DIR)/.venv; \
		echo "Created $(BACKEND_DIR)/.venv"; \
	fi
	$(BACKEND_DIR)/.venv/bin/pip install -e "$(BACKEND_DIR)[dev]"
	$(BACKEND_DIR)/.venv/bin/pip install requests

up: ## Start documented free Compose stack
	cd $(DOCKER_DIR) && DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 docker compose up --build -d $(FREE_STACK)

down: ## Stop Compose stack
	cd $(DOCKER_DIR) && docker compose down

test: ## Run backend pytest
	cd $(BACKEND_DIR) && pytest tests

smoke: ## Quick health smoke test
	@if [ -x $(BACKEND_DIR)/.venv/bin/python ]; then \
		$(BACKEND_DIR)/.venv/bin/python $(BACKEND_DIR)/scripts/smoke_test.py; \
	else \
		python3 $(BACKEND_DIR)/scripts/smoke_test.py; \
	fi

smoke-prod: ## Production smoke (BASE_URL + API_TOKEN required)
	@if [ -z "$${BASE_URL:-}" ]; then echo "BASE_URL is required" >&2; exit 1; fi
	@if [ -z "$${API_TOKEN:-}" ]; then echo "API_TOKEN is required" >&2; exit 1; fi
	@SMOKE_PROD=1 $(MAKE) smoke

boundary-checks: ## Boundary pytest bundle
	bash $(BACKEND_DIR)/scripts/boundary_checks.sh

migrate: ## Apply Alembic migrations
	cd $(BACKEND_DIR) && alembic upgrade head

integration-e2e: ## Backend Compose stack + frontend Playwright integration tests
	bash scripts/fullstack_e2e.sh

e2e-full-path: ## Full-path E2E (compose + fake sidecars; Task 78)
	@if [ -x $(BACKEND_DIR)/.venv/bin/python ]; then \
		$(BACKEND_DIR)/.venv/bin/python $(BACKEND_DIR)/scripts/e2e_full_path_runner.py --ci; \
	else \
		cd $(BACKEND_DIR) && python3 scripts/e2e_full_path_runner.py --ci; \
	fi
