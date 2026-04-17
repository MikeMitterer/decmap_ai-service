##
## DecisionMap — AI Service
##

SHELL  := /bin/bash
VENV   := .venv
PYTHON := $(VENV)/bin/python
PIP    := $(PYTHON) -m pip
PYTEST := $(VENV)/bin/pytest
RUFF   := $(VENV)/bin/ruff
UVICORN := $(VENV)/bin/uvicorn

-include ${DEV_MAKE}/colours.mk

# Fallbacks wenn DEV_MAKE nicht verfügbar (z.B. auf dem Server)
YELLOW ?= $(shell printf "\033[38;5;3m")
GREEN  ?= $(shell printf "\033[38;5;2m")
BLUE   ?= $(shell printf "\033[38;5;6m")
RED    ?= $(shell printf "\033[38;5;1m")
RESET  ?= $(shell printf "\033[0m")

.PHONY: help venv install install-dev lint format test test-unit test-contract test-integration \
        dev dev-up dev-down dev-logs \
        build build-amd64 push deploy rollback \
        db-migrate db-migrate-create db-migrate-status db-rollback \
        precheck version tags tag-major tag-minor tag-patch

##@ General

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\n$(YELLOW)Usage:$(RESET)\n  make $(BLUE)<target>$(RESET)\n"} \
		/^[a-zA-Z0-9_-]+:.*?##/ { printf "$(THEME_INDENT_TARGET)$(THEME_COLOR_TARGET)%-22s$(RESET) $(THEME_COLOR_DESC)%s$(RESET)\n", $$1, $$2 } \
		/^##@/ { printf "\n$(THEME_INDENT_GROUP)$(THEME_COLOR_GROUP)%s$(RESET)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

# ─── Precheck ───────────────────────────────────────────────────────────────

precheck:
	@if [[ -z "$${BASH_LIBS+x}" ]]; then \
		echo ""; \
		echo "$(RED)Achtung: '$(YELLOW)BASH_LIBS$(RED)' ist nicht gesetzt!$(RESET)"; \
		echo ""; \
		exit 1; \
	fi


##@ Hints

hints: ## Show useful links and URLs
	@echo
	@printf "  $(YELLOW)GitHub$(RESET)\n"
	@echo
	@printf "    $(BLUE)%-14s$(RESET) %s\n" "Repo"         "https://github.com/MikeMitterer/decmap_ai-service"
	@printf "    $(BLUE)%-14s$(RESET) %s\n" "Docker Image" "https://github.com/users/mangolila/packages/container/package/decisionmap-ai-service"
	@echo
	@printf "  $(YELLOW)URLs (nach make dev)$(RESET)\n"
	@echo
	@printf "    $(BLUE)%-14s$(RESET) %s\n" "API"   "http://localhost:8000"
	@printf "    $(BLUE)%-14s$(RESET) %s\n" "Docs"  "http://localhost:8000/docs"
	@printf "    $(BLUE)%-14s$(RESET) %s\n" "ReDoc" "http://localhost:8000/redoc"
	@echo
	@printf "  $(YELLOW)Testen ohne UI-Workflow$(RESET)\n"
	@echo
	@printf "    $(BLUE)%-14s$(RESET) %s\n" "Smoke Test"   "scripts/smoke-test.sh --help"
	@printf "    $(BLUE)%-14s$(RESET) %s\n" "Alle Tests"   "scripts/smoke-test.sh all"
	@printf "    $(BLUE)%-14s$(RESET) %s\n" "curl-Beisp."  "docs/cmdline.md  (im Root-Repo)"
	@printf "    $(BLUE)%-14s$(RESET) %s\n" "WebSocket"    "websocat ws://localhost:8000/ws  (brew install websocat)"
	@echo

# File-based sentinel — Make runs this recipe only when .venv/bin/python is missing.
# Creates the venv AND installs all dependencies so every dependent target
# finds its tools (pytest, ruff, uvicorn) on the first run after a clean checkout.
# All targets that use venv tools declare it as a prerequisite.
$(VENV)/bin/python:
	python3.11 -m venv $(VENV)
	$(VENV)/bin/pip install -r requirements.txt -r requirements-dev.txt

install install-dev lint format dev \
test test-unit test-contract test-integration: $(VENV)/bin/python

##@ Development

venv: $(VENV)/bin/python ## .venv erstellen — wird automatisch ausgeführt wenn ein Target es benötigt

install: ## Install production dependencies
	@$(PIP) install -r requirements.txt

install-dev: ## Install all dependencies (production + dev)
	@$(PIP) install -r requirements.txt -r requirements-dev.txt

lint: ## Run ruff linter
	@$(RUFF) check app/ tests/ main.py

format: ## Run ruff formatter
	@$(RUFF) format app/ tests/ main.py

dev: ## Start development server with auto-reload
	@$(UVICORN) main:app --host 0.0.0.0 --port 8000 --reload

##@ Testing

test: ## Run all tests
	@$(PYTEST) tests/ -v

test-unit: ## Run unit tests only
	@$(PYTEST) tests/unit/ -v

test-contract: ## Run contract tests only (requires API keys)
	@$(PYTEST) tests/contract/ -v

test-integration: ## Run integration tests (startet Test-Postgres auf Port 5433)
	docker compose -f docker-compose.test.yml up -d postgres
	@echo "Warte auf Test-Postgres ..."
	@until [ "$$(docker inspect --format='{{.State.Health.Status}}' decisionmap-ai-test-postgres 2>/dev/null)" = "healthy" ]; do \
	  sleep 2; \
	done
	POSTGRES_URL=postgresql://test:test@localhost:5433/decisionmap_test $(PYTEST) tests/ -v; \
	  _exit=$$?; \
	  docker compose -f docker-compose.test.yml down -v; \
	  exit $$_exit

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

##@ Entwicklung (Docker)

dev-up: ## Dev-Umgebung starten (Postgres + AI-Service)
	docker compose up -d

dev-down: ## Dev-Umgebung stoppen
	docker compose down

dev-logs: ## Dev-Logs anzeigen
	docker compose logs -f

##@ Build & Deploy

build: ## Docker-Image bauen — Multi-Arch (amd64 + arm64), direkt gepusht
	./docker/build.sh --build all

build-amd64: ## Docker-Image bauen — linux/amd64 only (Jenkins / CI)
	./docker/build.sh --build x86

push: ## Image in ghcr.io pushen (nach build-amd64)
	./docker/build.sh --push

##@ Versionierung

.PHONY: version
version: ## Aktuelle Version anzeigen (pyproject.toml + git tag)
	@echo
	@VER=$$(awk -F'"' '/^version /{print $$2}' pyproject.toml 2>/dev/null); \
	 [[ -z "$$VER" ]] && VER='nicht gesetzt'; \
	 TAG=$$(git describe --tags --abbrev=0 2>/dev/null || echo 'kein Tag'); \
	 echo "    ${YELLOW}pyproject${RESET}    = ${BLUE}$$VER${RESET}"; \
	 echo "    ${YELLOW}git tag${RESET}      = ${BLUE}$$TAG${RESET}"
	@echo

.PHONY: tags
tags: ## Letzte 10 Tags mit Message anzeigen
	@echo
	@git tag --sort=-version:refname -n1 | head -10 | \
	  awk '{printf "    \033[34m%-28s\033[0m \033[32m%s\033[0m\n", $$1, substr($$0, index($$0,$$2))}'
	@echo

.PHONY: tag-major
tag-major: precheck ## Version hochzählen — Major (X.y.z → X+1.0.0)  [MSG="..."]
	source "$${BASH_LIBS}/version.lib.sh" && semVerBump major auto "" "$${MSG:-}"

.PHONY: tag-minor
tag-minor: precheck ## Version hochzählen — Minor (x.Y.z → x.Y+1.0)  [MSG="..."]
	source "$${BASH_LIBS}/version.lib.sh" && semVerBump minor auto "" "$${MSG:-}"

.PHONY: tag-patch
tag-patch: precheck ## Version hochzählen — Patch (x.y.Z → x.y.Z+1)  [MSG="..."]
	source "$${BASH_LIBS}/version.lib.sh" && semVerBump patch auto "" "$${MSG:-}"
