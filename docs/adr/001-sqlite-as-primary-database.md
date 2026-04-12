# ADR-001: SQLite as Primary Database

**Status:** Accepted  
**Date:** 2026-03-30  
**Author:** ร้อยตำรวจเอกณัฐวุฒิ สาหร่ายทอง

## Context
BSIE needs a database that works as a local-first desktop application for Thai police investigators. The system must handle bank statements with 1,000-50,000 transactions per account.

## Decision
Use **SQLite** with WAL mode as the sole database engine.

## Rationale
- **Zero configuration** — no separate DB server to install/manage
- **Portable** — single file, easy to backup/restore/share
- **Sufficient performance** — WAL mode handles concurrent reads well
- **PyInstaller compatible** — bundles cleanly with the desktop app
- **Evidence preservation** — single file = complete evidence package

## Consequences
- Limited to ~500K transactions before performance degrades
- No multi-user concurrent write support (acceptable for single-analyst use)
- If scaling needed, migrate to PostgreSQL via Alembic (schema is compatible)

## Alternatives Considered
- **PostgreSQL** — overkill for local-first desktop app
- **Neo4j** — optional add-on for graph analysis, not primary store
