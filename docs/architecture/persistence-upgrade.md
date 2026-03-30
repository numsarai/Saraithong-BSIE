# BSIE Persistence Upgrade

## Current architecture preserved
- FastAPI remains the backend surface in `app.py`.
- The React analyst app remains the UI shell in `frontend/src/App.tsx`.
- The existing parser, normalization, reconciliation, and export flow remains centered on `pipeline/process_account.py`.
- Legacy SQLite-backed helpers for jobs, mapping memory, bank fingerprints, and overrides remain available through `database.py`.

## Migration strategy
- Introduce a new SQLAlchemy 2 persistence core under `persistence/`.
- Keep `database.py` as a compatibility facade so old callers do not need to change immediately.
- Persist uploads into a permanent evidence store before processing.
- Create a `files` row and a `parser_runs` row before background processing begins.
- Persist raw rows, normalized transactions, statement batches, duplicate groups, and match candidates after the existing pipeline finishes.
- Keep current CSV/XLSX output generation in place while new DB-backed search and export endpoints come online.

## Compatibility risks
- The project now supports PostgreSQL through `DATABASE_URL`, but still falls back to SQLite for local/dev continuity.
- Legacy tables remain present; new investigation tables are additive.
- Existing results can still be read from output files even before all historical runs are reprocessed into the new schema.

## Forensic integrity rules
- Original files are stored on disk as evidence artifacts.
- Raw rows are persisted separately from normalized transactions.
- Duplicate detection is additive and reviewable, never destructive.
- Manual corrections are logged in `audit_logs` and `review_decisions`.
- Reprocessing creates a new `parser_runs` record rather than replacing prior lineage.
