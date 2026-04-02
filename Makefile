##
## DecisionMap — AI Service
##

SHELL  := /bin/bash
PYTHON := python3.11
PIP    := $(PYTHON) -m pip

# Colors
GREEN  := \033[0;32m
BLUE   := \033[0;34m
YELLOW := \033[0;33m
RED    := \033[0;31m
RESET  := \033[0m

.PHONY: help install install-dev lint format test test-unit test-contract \
        dev build db-migrate db-migrate-create db-migrate-status db-rollback \
        docker-up docker-down \
        precheck version tags tag-major tag-minor tag-patch

##@ General

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\n$(YELLOW)Usage:$(RESET)\n  make $(BLUE)<target>$(RESET)\n"} \
		/^[a-zA-Z_-]+:.*?##/ { printf "  $(BLUE)%-22s$(RESET) $(GREEN)%s$(RESET)\n", $$1, $$2 } \
		/^##@/ { printf "\n$(YELLOW)%s$(RESET)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

# ─── Precheck ───────────────────────────────────────────────────────────────

precheck:
	@if [[ -z "$${BASH_LIBS+x}" ]]; then \
		echo ""; \
		echo "$(RED)Achtung: '$(YELLOW)BASH_LIBS$(RED)' ist nicht gesetzt!$(RESET)"; \
		echo ""; \
		exit 1; \
	fi

##@ Development

install: ## Install production dependencies
	@$(PIP) install -r requirements.txt

install-dev: ## Install all dependencies (production + dev)
	@$(PIP) install -r requirements.txt -r requirements-dev.txt

lint: ## Run ruff linter
	@ruff check app/ tests/ main.py

format: ## Run ruff formatter
	@ruff format app/ tests/ main.py

dev: ## Start development server with auto-reload
	@uvicorn main:app --host 0.0.0.0 --port 8000 --reload

##@ Testing

test: ## Run all tests
	@pytest tests/ -v

test-unit: ## Run unit tests only
	@pytest tests/unit/ -v

test-contract: ## Run contract tests only (requires API keys)
	@pytest tests/contract/ -v

##@ Database

db-migrate: ## Run pending Alembic migrations
	@alembic -c database/alembic.ini upgrade head

db-migrate-create: ## Create a new migration — NAME=<name> required
	@test -n "$(NAME)" || (echo "Error: NAME not set. Usage: make db-migrate-create NAME=description" && exit 1)
	@alembic -c database/alembic.ini revision --autogenerate -m "$(NAME)"

db-migrate-status: ## Show current migration status
	@alembic -c database/alembic.ini current

db-rollback: ## Roll back the last migration
	@alembic -c database/alembic.ini downgrade -1

##@ Docker

build: ## Build the Docker image
	@bash docker/build.sh

docker-up: ## Start services via docker-compose
	@docker compose up -d

docker-down: ## Stop services via docker-compose
	@docker compose down

##@ Versioning

version: ## Show current version (pyproject.toml + git tag)
	@echo
	@VER=$$(grep '^version' pyproject.toml 2>/dev/null | head -1 | sed 's/.*= *"//;s/".*//'); \
	 [[ -z "$$VER" ]] && VER='nicht gesetzt'; \
	 TAG=$$(git describe --tags --abbrev=0 2>/dev/null || echo 'kein Tag'); \
	 printf "    \033[0;33mpyproject\033[0m    = \033[0;34m$$VER\033[0m\n"; \
	 printf "    \033[0;33mgit tag\033[0m      = \033[0;34m$$TAG\033[0m\n"
	@echo

tags: ## Show last 10 tags with message
	@echo
	@git tag --sort=-version:refname -n1 | head -10 | \
	  awk '{printf "    \033[34m%-28s\033[0m \033[32m%s\033[0m\n", $$1, substr($$0, index($$0,$$2))}'
	@echo

tag-major: precheck ## Bump major version (26.3.0 → 27.0.0)  [MSG="..."]
	source "$${BASH_LIBS}/version.lib.sh" && bumpVer major auto "" current "$${MSG:-}"

tag-minor: precheck ## Bump minor version (26.3.0 → 26.4.0)  [MSG="..."]
	source "$${BASH_LIBS}/version.lib.sh" && bumpVer minor auto "" current "$${MSG:-}"

tag-patch: precheck ## Bump patch version (26.3.0 → 26.3.1)  [MSG="..."]
	source "$${BASH_LIBS}/version.lib.sh" && bumpVer patch auto "" current "$${MSG:-}"
