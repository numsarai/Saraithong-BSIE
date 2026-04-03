# BSIE Agents

This file defines the practical agent roles for working inside BSIE.

## Core Principle

All agents must preserve evidentiary integrity first. Raw source values, lineage, audit logs, and review history are not optional.

## Primary Agents

### 1. Intake Agent

Use for:
- upload flow
- file hashing
- bank detection
- column mapping confirmation
- parser run creation

Primary modules:
- [`/Users/saraithong/Documents/bsie/app.py`](/Users/saraithong/Documents/bsie/app.py)
- [`/Users/saraithong/Documents/bsie/services/file_ingestion_service.py`](/Users/saraithong/Documents/bsie/services/file_ingestion_service.py)
- [`/Users/saraithong/Documents/bsie/services/persistence_pipeline_service.py`](/Users/saraithong/Documents/bsie/services/persistence_pipeline_service.py)

Success criteria:
- file evidence stored
- `files` row created
- `parser_runs` row created
- raw rows persisted when available

### 2. Normalization Agent

Use for:
- statement extraction
- standard schema mapping
- account parsing
- reconciliation

Primary modules:
- [`/Users/saraithong/Documents/bsie/pipeline/process_account.py`](/Users/saraithong/Documents/bsie/pipeline/process_account.py)
- [`/Users/saraithong/Documents/bsie/core/normalizer.py`](/Users/saraithong/Documents/bsie/core/normalizer.py)
- [`/Users/saraithong/Documents/bsie/core/reconciliation.py`](/Users/saraithong/Documents/bsie/core/reconciliation.py)

Success criteria:
- normalized transactions persisted
- lineage preserved
- output package still produced

### 3. Intelligence Agent

Use for:
- duplicate detection
- account resolution
- transaction matching
- entity/link graph preparation

Primary modules:
- [`/Users/saraithong/Documents/bsie/services/search_service.py`](/Users/saraithong/Documents/bsie/services/search_service.py)
- [`/Users/saraithong/Documents/bsie/services/export_service.py`](/Users/saraithong/Documents/bsie/services/export_service.py)
- [`/Users/saraithong/Documents/bsie/core/graph_export.py`](/Users/saraithong/Documents/bsie/core/graph_export.py)

Success criteria:
- duplicates remain additive
- inferred matches stay reversible
- graph output is stable and i2-safe

### 4. Review Agent

Use for:
- duplicate review
- match review
- transaction correction
- account correction
- audit inspection

Primary modules:
- [`/Users/saraithong/Documents/bsie/services/review_service.py`](/Users/saraithong/Documents/bsie/services/review_service.py)
- [`/Users/saraithong/Documents/bsie/services/audit_service.py`](/Users/saraithong/Documents/bsie/services/audit_service.py)
- [`/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.tsx)

Success criteria:
- every manual change is audited
- no destructive overwrite without history

### 5. Platform Agent

Use for:
- database runtime
- backup/reset/restore
- scheduled backup policy
- local desktop/runtime hardening

Primary modules:
- [`/Users/saraithong/Documents/bsie/persistence/base.py`](/Users/saraithong/Documents/bsie/persistence/base.py)
- [`/Users/saraithong/Documents/bsie/services/admin_service.py`](/Users/saraithong/Documents/bsie/services/admin_service.py)
- [`/Users/saraithong/Documents/bsie/main_launcher.py`](/Users/saraithong/Documents/bsie/main_launcher.py)

Success criteria:
- runtime backend visible
- backups reproducible
- restore preview available
- scheduled backup policy persisted

## Coordination Rules

- Do not change parser semantics and persistence semantics in the same patch unless the change is fully regression-tested.
- Keep file-based exports working even when DB-backed retrieval changes.
- Review and audit changes must never mutate raw evidence rows.
- Graph export changes require tests for schema, IDs, direction, lineage, and inferred/confirmed safety.
