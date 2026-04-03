# BSIE Architecture

## Runtime Shape

BSIE is a FastAPI + React investigation platform with a database-backed evidence layer and a file-based export layer.

## Main Layers

### 1. Web/API Layer

- FastAPI entrypoint: [`/Users/saraithong/Documents/bsie/app.py`](/Users/saraithong/Documents/bsie/app.py)
- React analyst UI: [`/Users/saraithong/Documents/bsie/frontend/src/App.tsx`](/Users/saraithong/Documents/bsie/frontend/src/App.tsx)
- Investigation admin: [`/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.tsx)

### 2. Persistence Layer

- SQLAlchemy runtime base: [`/Users/saraithong/Documents/bsie/persistence/base.py`](/Users/saraithong/Documents/bsie/persistence/base.py)
- Investigation tables: [`/Users/saraithong/Documents/bsie/persistence/models.py`](/Users/saraithong/Documents/bsie/persistence/models.py)
- Legacy compatibility tables: [`/Users/saraithong/Documents/bsie/persistence/legacy_models.py`](/Users/saraithong/Documents/bsie/persistence/legacy_models.py)
- Compatibility facade: [`/Users/saraithong/Documents/bsie/database.py`](/Users/saraithong/Documents/bsie/database.py)

### 3. Pipeline Layer

- Primary processing flow: [`/Users/saraithong/Documents/bsie/pipeline/process_account.py`](/Users/saraithong/Documents/bsie/pipeline/process_account.py)
- Load/detect/map/normalize modules live under [`/Users/saraithong/Documents/bsie/core`](/Users/saraithong/Documents/bsie/core)

### 4. Investigation Services

- ingestion and parser-run persistence
- review and audit
- search and retrieval
- export jobs
- admin backup/reset/restore

These are in [`/Users/saraithong/Documents/bsie/services`](/Users/saraithong/Documents/bsie/services).

## Data Flow

1. upload file
2. hash and persist evidence metadata
3. detect bank and mapping
4. create parser run
5. process statement through pipeline
6. persist raw rows, batch, accounts, transactions, duplicates, matches
7. write output package
8. expose search/review/export through API and UI

## Storage Model

### Evidence on disk

- uploaded source evidence
- export packages
- bulk run outputs
- backup artifacts

### Evidence in database

- files
- parser runs
- raw rows
- statement batches
- accounts
- transactions
- matches
- review decisions
- audit logs
- export jobs
- admin settings

## Operational Modes

### Default runtime

- SQLite local-only mode by default via `BSIE_LOCAL_ONLY=1`
- `DATABASE_URL` is only used when local-only mode is explicitly disabled

### Backup modes

- `json`
- `pg_dump`
- `auto`

`auto` prefers PostgreSQL dump mode only when usable tools are available. Otherwise it falls back to JSON safely.
