# BSIE – Bank Statement Intelligence Engine

## Overview

Financial intelligence platform for Thai police investigators. Processes bank statements from 8 Thai banks, builds transaction networks, detects suspicious patterns, generates court-ready reports. Serves as a standalone data source module for SPNI via `/api/spni/*`.

## Tech Stack

- **Backend:** FastAPI + SQLAlchemy 2 + SQLite (WAL) — 22 routers, 28 services, 125+ endpoints
- **Frontend:** React 19 + TypeScript + Vite + Tailwind CSS + Zustand + Cytoscape.js + Recharts
- **Tests:** 229 backend (pytest) + 32 frontend (vitest)
- **i18n:** Thai-first (react-i18next, fallbackLng: 'th')

## Key Architecture

- **Routers** (`routers/`) — `APIRouter` with `prefix`, `tags`, `dependencies=[Depends(require_auth)]`
- **Services** (`services/`) — Pure functions, `Session` as first param, return dicts
- **DB Session** — `with get_db_session() as session:` context manager
- **Pipeline** — 14-step processing: load → detect → normalize → NLP → classify → link → export
- **Models** — 20 SQLAlchemy 2 mapped classes in `persistence/models.py`

## Conventions

- All endpoint functions: `async def api_xxx()`
- All responses: `JSONResponse(dict)`
- Parser run status values: `"queued"`, `"running"`, `"done"`
- Direction values: `"IN"`, `"OUT"`
- Auth: opt-in via `BSIE_AUTH_REQUIRED=true` env var
- Dates: timezone-aware UTC, `.isoformat()` for serialization
- Decimals: `float()` before JSON serialization

## Critical Files

- `app.py` — App setup, middleware, router registration (UI router must be last)
- `persistence/models.py` — All 20 SQLAlchemy models
- `persistence/base.py` — `get_db_session()`, `Base`, `utcnow()`
- `services/auth_service.py` — `require_auth` dependency
- `routers/spni.py` + `services/spni_service.py` — SPNI integration API

## Running

```bash
source .venv/bin/activate
uvicorn app:app --host 127.0.0.1 --port 8757
```

## Testing

```bash
.venv/bin/python -m pytest tests/ -x
```

## Important Notes

- Data is law enforcement classified — no external API calls, self-hosted only
- `Entity` model has no `identifier_type` column — only `entity_type` + `identifier_value`
- CORS allows: localhost:6776 (frontend dev), localhost:8757 (same-origin), localhost:3000 (SPNI)
- File upload allowlist: .xlsx, .xls, .ofx, .pdf, .png, .jpg, .jpeg, .bmp (no .csv)

## Related Docs

- [ARCHITECTURE.md](ARCHITECTURE.md) — System design, data flow, component diagram
- [FEATURES.md](FEATURES.md) — Feature reference table
- [DOMAIN_RULES.md](DOMAIN_RULES.md) — Business logic constraints
- [AGENTS.md](AGENTS.md) — Agent orchestration guide
- [docs/adr/](docs/adr/) — Architecture Decision Records
- [docs/HANDOFF.md](docs/HANDOFF.md) — Agent session handoff state
- [docs/DECISIONS.md](docs/DECISIONS.md) — Technical decision log
