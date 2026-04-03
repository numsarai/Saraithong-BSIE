# BSIE Tasks

## Active Operational Tasks

### 1. Intake and Parsing

- ingest Excel and OFX files
- detect bank and mapping
- persist parser runs and raw rows
- process single-account and bulk folder workflows

### 2. Investigation Review

- review duplicate groups
- review match candidates
- correct accounts and transactions
- inspect audit logs

### 3. Export and Graph Analysis

- generate transaction exports
- generate duplicate and unresolved-match review exports
- generate graph CSV and i2 ANX exports
- generate BSIE graph analysis JSON/XLSX/API views from normalized transactions
- validate graph direction and lineage safety

### 4. Platform Operations

- check DB runtime and schema readiness
- create backups
- preview restore impact
- reset and restore database
- manage scheduled backup policy
- manage backup retention

## Immediate Engineering Backlog

- add per-table restore tooling only if a strong investigation need appears
- add golden-case fixtures for backup retention and admin settings UI
- add backup job history view in Investigation Admin

## Done and Stabilized

- persistent investigation schema
- parser run history
- duplicate detection
- account registry
- match candidate generation
- audit-safe review workflow
- graph/i2 hardening
- internal BSIE Graph Analysis Module
- local-only SQLite runtime hardening
- backup/reset/restore UI
- scheduled backup settings persistence
