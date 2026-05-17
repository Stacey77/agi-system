.PHONY: install install-dev env run dev test test-unit test-integration test-perf test-cov lint format typecheck clean health help

PYTHON  ?= python3
PIP     ?= pip
UVICORN ?= uvicorn
PORT    ?= 8000

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Usage: make <target>"

install: ## Install production dependencies
	$(PIP) install -r requirements.txt

install-dev: ## Install development dependencies
	$(PIP) install -r requirements.txt -r requirements-dev.txt

env: ## Copy .env.example to .env if .env doesn't exist
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example — please fill in your API keys")

run: env ## Start the API server (production mode)
	$(UVICORN) src.api.main:app --host 0.0.0.0 --port $(PORT)

dev: env ## Start the API server with auto-reload
	$(UVICORN) src.api.main:app --host 0.0.0.0 --port $(PORT) --reload

test: ## Run all tests
	$(PYTHON) -m pytest tests/ -v

test-unit: ## Run unit tests only
	$(PYTHON) -m pytest tests/unit/ -v

test-integration: ## Run integration tests only
	$(PYTHON) -m pytest tests/integration/ -v

test-perf: ## Run performance tests only
	$(PYTHON) -m pytest tests/performance/ -v

test-cov: ## Run tests with coverage report
	$(PYTHON) -m pytest tests/ --cov=src --cov-report=term-missing --cov-report=html

lint: ## Run ruff linter
	$(PYTHON) -m ruff check src/ tests/

format: ## Auto-format with ruff
	$(PYTHON) -m ruff format src/ tests/

typecheck: ## Run mypy type checks
	$(PYTHON) -m mypy src/ --ignore-missing-imports

clean: ## Remove __pycache__ and build artefacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache htmlcov .coverage

health: ## Hit the health endpoint (server must be running)
	curl -s http://localhost:$(PORT)/api/v1/health | $(PYTHON) -m json.tool
