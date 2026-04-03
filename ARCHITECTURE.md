# BSIE Architecture

## Runtime Shape

BSIE is a local-first FastAPI + React investigation platform with:

- a database-backed evidence and investigation layer
- a file-based export/output layer
- a deterministic learning layer for bank fingerprints, mapping profiles, and account identity memory

The current default runtime is local SQLite only.

## Main Entrypoints

### Backend

- API entrypoint: [`/Users/saraithong/Documents/bsie/app.py`](/Users/saraithong/Documents/bsie/app.py)
- background job wrapper: [`/Users/saraithong/Documents/bsie/tasks.py`](/Users/saraithong/Documents/bsie/tasks.py)
- pipeline orchestrator: [`/Users/saraithong/Documents/bsie/pipeline/process_account.py`](/Users/saraithong/Documents/bsie/pipeline/process_account.py)

### Frontend

- app shell: [`/Users/saraithong/Documents/bsie/frontend/src/App.tsx`](/Users/saraithong/Documents/bsie/frontend/src/App.tsx)
- global state: [`/Users/saraithong/Documents/bsie/frontend/src/store.ts`](/Users/saraithong/Documents/bsie/frontend/src/store.ts)
- API client layer: [`/Users/saraithong/Documents/bsie/frontend/src/api.ts`](/Users/saraithong/Documents/bsie/frontend/src/api.ts)

## Backend Layers

### 1. API And Workflow Orchestration

[`/Users/saraithong/Documents/bsie/app.py`](/Users/saraithong/Documents/bsie/app.py) owns:

- upload and mapping-confirm endpoints
- process and process-folder dispatch
- review/search/admin/export endpoints
- download endpoints
- bridge logic between frontend payloads and service/pipeline layers

### 2. Intake And Evidence Persistence

Primary modules:

- [`/Users/saraithong/Documents/bsie/services/file_ingestion_service.py`](/Users/saraithong/Documents/bsie/services/file_ingestion_service.py)
- [`/Users/saraithong/Documents/bsie/services/persistence_pipeline_service.py`](/Users/saraithong/Documents/bsie/services/persistence_pipeline_service.py)

Responsibilities:

- persist uploaded source files under evidence storage
- compute SHA-256 hashes
- create `files` and `parser_runs`
- persist raw rows, statement batches, accounts, transactions, entities, and links
- keep parser-run history and reproducible export metadata

### 3. Parsing And Normalization Pipeline

Primary modules:

- [`/Users/saraithong/Documents/bsie/pipeline/process_account.py`](/Users/saraithong/Documents/bsie/pipeline/process_account.py)
- [`/Users/saraithong/Documents/bsie/core/loader.py`](/Users/saraithong/Documents/bsie/core/loader.py)
- [`/Users/saraithong/Documents/bsie/core/bank_detector.py`](/Users/saraithong/Documents/bsie/core/bank_detector.py)
- [`/Users/saraithong/Documents/bsie/core/column_detector.py`](/Users/saraithong/Documents/bsie/core/column_detector.py)
- [`/Users/saraithong/Documents/bsie/core/normalizer.py`](/Users/saraithong/Documents/bsie/core/normalizer.py)
- [`/Users/saraithong/Documents/bsie/core/ofx_io.py`](/Users/saraithong/Documents/bsie/core/ofx_io.py)
- [`/Users/saraithong/Documents/bsie/core/classifier.py`](/Users/saraithong/Documents/bsie/core/classifier.py)
- [`/Users/saraithong/Documents/bsie/core/link_builder.py`](/Users/saraithong/Documents/bsie/core/link_builder.py)
- [`/Users/saraithong/Documents/bsie/core/entity.py`](/Users/saraithong/Documents/bsie/core/entity.py)

Responsibilities:

- read Excel and OFX
- detect bank and header row/sheet
- suggest logical column mappings
- normalize dates, amounts, descriptions, and account fields
- enrich transactions with NLP and classification hints
- build link-ready `from_account` and `to_account` columns
- write account-level output packages

### 4. Investigation Services

Primary modules:

- [`/Users/saraithong/Documents/bsie/services/review_service.py`](/Users/saraithong/Documents/bsie/services/review_service.py)
- [`/Users/saraithong/Documents/bsie/services/audit_service.py`](/Users/saraithong/Documents/bsie/services/audit_service.py)
- [`/Users/saraithong/Documents/bsie/services/search_service.py`](/Users/saraithong/Documents/bsie/services/search_service.py)
- [`/Users/saraithong/Documents/bsie/services/export_service.py`](/Users/saraithong/Documents/bsie/services/export_service.py)
- [`/Users/saraithong/Documents/bsie/services/admin_service.py`](/Users/saraithong/Documents/bsie/services/admin_service.py)

Responsibilities:

- manual review and correction
- append-only audit logging
- duplicate and match retrieval
- export job generation
- backup/reset/restore operations
- graph and learning-feedback retrieval

### 5. Learning And Memory

Primary modules:

- [`/Users/saraithong/Documents/bsie/core/bank_memory.py`](/Users/saraithong/Documents/bsie/core/bank_memory.py)
- [`/Users/saraithong/Documents/bsie/core/mapping_memory.py`](/Users/saraithong/Documents/bsie/core/mapping_memory.py)
- [`/Users/saraithong/Documents/bsie/services/account_resolution_service.py`](/Users/saraithong/Documents/bsie/services/account_resolution_service.py)

Responsibilities:

- save reusable bank fingerprints
- save reusable mapping profiles
- remember account holder names and account identities
- learn only from deterministic or analyst-confirmed signals
- expose learning signals through audit-safe records

## Frontend Surfaces

### Wizard

The default workflow is a 5-step analyst wizard:

1. upload file
2. review bank detection and mapping
3. configure account context
4. poll processing status
5. inspect results

Primary files:

- [`/Users/saraithong/Documents/bsie/frontend/src/components/steps/Step1Upload.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/steps/Step1Upload.tsx)
- [`/Users/saraithong/Documents/bsie/frontend/src/components/steps/Step2Map.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/steps/Step2Map.tsx)
- [`/Users/saraithong/Documents/bsie/frontend/src/components/steps/Step3Config.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/steps/Step3Config.tsx)
- [`/Users/saraithong/Documents/bsie/frontend/src/components/steps/Step4Processing.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/steps/Step4Processing.tsx)
- [`/Users/saraithong/Documents/bsie/frontend/src/components/steps/Step5Results.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/steps/Step5Results.tsx)

### Investigation/Admin

Primary file:

- [`/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.tsx)

Responsibilities:

- database and backup operations
- file and parser-run inspection
- account and transaction review
- audit and learning-feedback inspection
- graph analysis and export job operations

### Additional Surfaces

- bulk intake: [`/Users/saraithong/Documents/bsie/frontend/src/components/BulkIntake.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/BulkIntake.tsx)
- bank manager: [`/Users/saraithong/Documents/bsie/frontend/src/components/BankManager.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/BankManager.tsx)
- sidebar navigation: [`/Users/saraithong/Documents/bsie/frontend/src/components/Sidebar.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/Sidebar.tsx)

## Data Flow

### Single-file Intake

1. upload file
2. persist evidence and compute file hash
3. detect bank, detect columns, and merge memory-assisted suggestions
4. confirm mapping and create parser run
5. dispatch local background processing
6. normalize and enrich transactions
7. persist raw rows, batches, accounts, transactions, entities, duplicates, and matches
8. write output package and export-ready artifacts
9. expose search, review, audit, and export views through API and UI

### Review Loop

1. analyst reviews duplicates, matches, transactions, or accounts
2. review service writes append-only audit rows and review decisions
3. deterministic learning signals may be recorded for reusable memory
4. original raw evidence rows remain untouched

## Storage Model

### Evidence On Disk

- uploaded source evidence
- output packages
- export job outputs
- bulk run outputs
- JSON backups

### Evidence In Database

- files
- parser runs
- raw import rows
- statement batches
- accounts
- transactions
- entities and account/entity links
- duplicate groups
- transaction matches
- review decisions
- audit logs
- export jobs
- admin settings

### Compatibility Layer

BSIE still carries a compatibility facade for legacy callers:

- [`/Users/saraithong/Documents/bsie/database.py`](/Users/saraithong/Documents/bsie/database.py)
- [`/Users/saraithong/Documents/bsie/persistence/legacy_models.py`](/Users/saraithong/Documents/bsie/persistence/legacy_models.py)

This is useful, but it is also a shared-risk area for refactors.

## High-Risk Shared Modules

These modules should usually have a single owner in multi-agent work:

- [`/Users/saraithong/Documents/bsie/app.py`](/Users/saraithong/Documents/bsie/app.py)
- [`/Users/saraithong/Documents/bsie/persistence/models.py`](/Users/saraithong/Documents/bsie/persistence/models.py)
- [`/Users/saraithong/Documents/bsie/persistence/schemas.py`](/Users/saraithong/Documents/bsie/persistence/schemas.py)
- [`/Users/saraithong/Documents/bsie/pipeline/process_account.py`](/Users/saraithong/Documents/bsie/pipeline/process_account.py)
- [`/Users/saraithong/Documents/bsie/frontend/src/api.ts`](/Users/saraithong/Documents/bsie/frontend/src/api.ts)
- [`/Users/saraithong/Documents/bsie/frontend/src/store.ts`](/Users/saraithong/Documents/bsie/frontend/src/store.ts)

## Subagent Implications

The current architecture suggests a small-team orchestration style:

- [`/Users/saraithong/Documents/bsie/app.py`](/Users/saraithong/Documents/bsie/app.py) should usually have one backend owner because it bridges many services and UI contracts.
- [`/Users/saraithong/Documents/bsie/pipeline/process_account.py`](/Users/saraithong/Documents/bsie/pipeline/process_account.py) should usually have one owner because pipeline order and evidence handling are tightly coupled.
- [`/Users/saraithong/Documents/bsie/frontend/src/api.ts`](/Users/saraithong/Documents/bsie/frontend/src/api.ts) and [`/Users/saraithong/Documents/bsie/frontend/src/store.ts`](/Users/saraithong/Documents/bsie/frontend/src/store.ts) should not be edited by multiple frontend builders at the same time.
- [`/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.tsx) is large enough to justify a dedicated admin/review UI owner for bigger tasks.

In practice, BSIE usually works best with:

1. one researcher or local survey pass
2. one backend owner for the contract path
3. one frontend owner only if UI changes are needed
4. one tester/reviewer

See the detailed policy in [`/Users/saraithong/Documents/bsie/AGENTS.md`](/Users/saraithong/Documents/bsie/AGENTS.md) and [`/Users/saraithong/Documents/bsie/docs/architecture/agent-orchestration.md`](/Users/saraithong/Documents/bsie/docs/architecture/agent-orchestration.md).
For reusable checklists and subagent brief templates, use [`/Users/saraithong/Documents/bsie/docs/architecture/subagent-checklists.md`](/Users/saraithong/Documents/bsie/docs/architecture/subagent-checklists.md).

## Related Documentation

- agent playbook: [`/Users/saraithong/Documents/bsie/AGENTS.md`](/Users/saraithong/Documents/bsie/AGENTS.md)
- domain constraints: [`/Users/saraithong/Documents/bsie/DOMAIN_RULES.md`](/Users/saraithong/Documents/bsie/DOMAIN_RULES.md)
- orchestration guide: [`/Users/saraithong/Documents/bsie/docs/architecture/agent-orchestration.md`](/Users/saraithong/Documents/bsie/docs/architecture/agent-orchestration.md)
