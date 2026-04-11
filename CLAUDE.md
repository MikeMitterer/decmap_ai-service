# CLAUDE.md — ai-service

> Sub-CLAUDE.md. Alle Konventionen und Architekturprinzipien stehen in:
> [`../CLAUDE.md`](../CLAUDE.md) (Haupt-Referenz) + [`../docs/`](../docs/) (Detail-Spezifikationen)

## Dieses Repo

FastAPI-Service für DecisionMap — KI-gestützte Aehnlichkeitserkennung, Clustering, Spam-Filter und WebSocket-Broadcasts.

## Lokale Entwicklung

**Voraussetzungen:** Python 3.11+, laufende PostgreSQL-Instanz (via `make -C ../backend dev-up`)

```bash
cp .env.example .env          # API-Keys und DB-URL eintragen
make install-dev              # Alle Abhaengigkeiten installieren
make dev                      # Dev-Server auf http://localhost:8000 (auto-reload)
```

## Befehle

```bash
make help                     # Alle verfuegbaren Befehle
make install                  # Nur Produktion-Abhaengigkeiten
make install-dev              # Produktion + Dev-Abhaengigkeiten
make lint                     # ruff check
make format                   # ruff format
make dev                      # uvicorn mit --reload
```

## Tests

```bash
make test                     # Alle Tests (unit + contract)
make test-unit                # Nur Unit-Tests (kein Netzwerk)
make test-contract            # Contract-Tests (benoetigen API-Keys in .env)
```

Test-Struktur in `tests/`:
- `unit/services/`  — Services mit gemocktem OpenAI/Embedding-Provider
- `unit/providers/` — Provider-Unit-Tests
- `contract/`       — Contract-Tests gegen echte API (OpenAI, Embedding)
- `fakedata/`       — Gemeinsame Fake-Daten (generiert via `make fakedata-sync`)

**Hinweis:** Optionale Dependencies (z. B. OpenAI-Client) auf Modul-Level importieren, nicht lokal in Funktionen — sonst greift `patch()` in Tests nicht.

## Datenbank-Migrationen (Alembic)

```bash
make db-migrate               # Ausstehende Migrationen ausfuehren
make db-migrate-create NAME=beschreibung  # Neue Migration erstellen
make db-migrate-status        # Aktuellen Migrationsstatus anzeigen
make db-rollback              # Letzte Migration zurueckrollen
```

Migrationen in `database/migrations/`. **Nie bestehende Migrationen editieren** — Breaking Changes zweistufig (additive Migration + separater Cleanup).

**Reihenfolge:** Alembic (`make db-migrate`) muss vor Directus Schema Apply laufen — sonst schlaegt `directus-schema-apply` fehl.

## Architektur

```
app/
├── routers/        ← HTTP-Endpunkte (nur Routing, keine Business Logic)
│   ├── similarity.py
│   ├── clustering.py
│   ├── hooks.py    ← Directus Webhook-Empfaenger
│   ├── websocket.py
│   └── health.py
├── services/       ← Business Logic
├── repositories/   ← DB-Zugriff via psycopg3
├── providers/      ← Externe APIs (OpenAI, Embedding)
├── models/         ← Pydantic Request/Response-Models
├── dependencies.py ← FastAPI Dependencies (DB-Connection, Auth)
└── config.py       ← Settings via pydantic-settings
```

## Webhook-Sicherheit

Alle Directus-Hook-Endpunkte via `_verify_webhook_secret()` Dependency absichern.
Leeres `WEBHOOK_SECRET` in `.env` = Dev-Mode (kein Check).

## Deploy

```bash
make build    # Docker-Image bauen (docker/build.sh — hashVer-Tagging)
```

Jenkins-Pipeline in `Jenkinsfile` — Reihenfolge: test → build → db-migrate → deploy.
`master` ist immer deploybar.
