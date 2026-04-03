# BSIE Agents

This file defines the practical agent roles and orchestration rules for working inside BSIE.

## Core Principle

All agents must preserve evidentiary integrity first. Raw source values, lineage, audit logs, review history, and reproducible exports are not optional.

## Current Project Reality

BSIE is not a flat codebase. It currently has a few strong chokepoints that should drive subagent policy:

- [`/Users/saraithong/Documents/bsie/app.py`](/Users/saraithong/Documents/bsie/app.py) is the backend integration hub for intake, review, admin, graph, download, and export endpoints.
- [`/Users/saraithong/Documents/bsie/pipeline/process_account.py`](/Users/saraithong/Documents/bsie/pipeline/process_account.py) is the sequential evidence-sensitive pipeline core.
- [`/Users/saraithong/Documents/bsie/services/persistence_pipeline_service.py`](/Users/saraithong/Documents/bsie/services/persistence_pipeline_service.py) and [`/Users/saraithong/Documents/bsie/persistence/models.py`](/Users/saraithong/Documents/bsie/persistence/models.py) define the persistent evidence contract.
- [`/Users/saraithong/Documents/bsie/frontend/src/api.ts`](/Users/saraithong/Documents/bsie/frontend/src/api.ts) and [`/Users/saraithong/Documents/bsie/frontend/src/store.ts`](/Users/saraithong/Documents/bsie/frontend/src/store.ts) are the frontend coupling and state chokepoints.
- [`/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.tsx) is the largest shared admin/review surface.

Subagent policy should optimize around these chokepoints first, not around abstract role names.

## Before Creating Subagents

1. Inspect the task and identify which layer it touches:
   - intake
   - normalization
   - intelligence
   - review
   - platform
   - frontend workflow
2. Identify shared files before assigning work.
3. Give each shared file one owner only.
4. Let non-owners read shared files, but route edits through the owner.
5. Do research before risky implementation.

Use the reusable checklist and prompt templates in [`/Users/saraithong/Documents/bsie/docs/architecture/subagent-checklists.md`](/Users/saraithong/Documents/bsie/docs/architecture/subagent-checklists.md) when you need a concrete spawn plan.

## Shared File Ownership Defaults

Use these defaults unless the task clearly needs something else:

- Backend API owner:
  - [`/Users/saraithong/Documents/bsie/app.py`](/Users/saraithong/Documents/bsie/app.py)
- Schema owner:
  - [`/Users/saraithong/Documents/bsie/persistence/models.py`](/Users/saraithong/Documents/bsie/persistence/models.py)
  - [`/Users/saraithong/Documents/bsie/persistence/schemas.py`](/Users/saraithong/Documents/bsie/persistence/schemas.py)
- Pipeline owner:
  - [`/Users/saraithong/Documents/bsie/pipeline/process_account.py`](/Users/saraithong/Documents/bsie/pipeline/process_account.py)
- Frontend integration owner:
  - [`/Users/saraithong/Documents/bsie/frontend/src/api.ts`](/Users/saraithong/Documents/bsie/frontend/src/api.ts)
  - [`/Users/saraithong/Documents/bsie/frontend/src/store.ts`](/Users/saraithong/Documents/bsie/frontend/src/store.ts)
- Review UI owner:
  - [`/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.tsx)
- Documentation owner:
  - all project markdown files

## Concurrency Budget

Use the smallest team shape that still keeps momentum:

- Tiny one-file change:
  - no subagents unless the file is risky and needs an independent reviewer
- Single-layer feature:
  - at most 1 builder + 1 tester
- Cross-layer feature with a stable contract:
  - 1 backend builder
  - 1 frontend builder
  - 1 testing/reviewer agent
- Schema, pipeline, or evidence-contract change:
  - 1 researcher
  - 1 builder
  - 1 tester
  - do not run parallel builders on the contract path

As a practical default, BSIE work should rarely need more than 4 active agents including the orchestrator.

## Quick Start Checklist

Before spawning any builder, do this in order:

1. name the affected layer
2. map shared files
3. assign a single owner per shared file
4. choose the smallest safe team shape
5. stabilize contracts before UI work
6. reserve testing as a separate scope when possible

The fill-in templates live in [`/Users/saraithong/Documents/bsie/docs/architecture/subagent-checklists.md`](/Users/saraithong/Documents/bsie/docs/architecture/subagent-checklists.md).

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
- export-ready normalized dataframe generation

Primary modules:
- [`/Users/saraithong/Documents/bsie/pipeline/process_account.py`](/Users/saraithong/Documents/bsie/pipeline/process_account.py)
- [`/Users/saraithong/Documents/bsie/core/normalizer.py`](/Users/saraithong/Documents/bsie/core/normalizer.py)
- [`/Users/saraithong/Documents/bsie/core/reconciliation.py`](/Users/saraithong/Documents/bsie/core/reconciliation.py)
- [`/Users/saraithong/Documents/bsie/core/ofx_io.py`](/Users/saraithong/Documents/bsie/core/ofx_io.py)

Success criteria:
- normalized transactions persisted
- raw lineage preserved
- output package still produced

### 3. Intelligence Agent

Use for:
- duplicate detection
- account resolution
- transaction matching
- mapping/profile learning
- graph preparation

Primary modules:
- [`/Users/saraithong/Documents/bsie/services/account_resolution_service.py`](/Users/saraithong/Documents/bsie/services/account_resolution_service.py)
- [`/Users/saraithong/Documents/bsie/services/search_service.py`](/Users/saraithong/Documents/bsie/services/search_service.py)
- [`/Users/saraithong/Documents/bsie/services/export_service.py`](/Users/saraithong/Documents/bsie/services/export_service.py)
- [`/Users/saraithong/Documents/bsie/core/bank_memory.py`](/Users/saraithong/Documents/bsie/core/bank_memory.py)
- [`/Users/saraithong/Documents/bsie/core/mapping_memory.py`](/Users/saraithong/Documents/bsie/core/mapping_memory.py)
- [`/Users/saraithong/Documents/bsie/core/graph_export.py`](/Users/saraithong/Documents/bsie/core/graph_export.py)

Success criteria:
- duplicates remain additive
- inferred matches stay reversible
- graph output is stable and i2-safe
- learning signals are deterministic and auditable

### 4. Review Agent

Use for:
- duplicate review
- match review
- transaction correction
- account correction
- audit inspection
- learning feedback inspection

Primary modules:
- [`/Users/saraithong/Documents/bsie/services/review_service.py`](/Users/saraithong/Documents/bsie/services/review_service.py)
- [`/Users/saraithong/Documents/bsie/services/audit_service.py`](/Users/saraithong/Documents/bsie/services/audit_service.py)
- [`/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.tsx)

Success criteria:
- every manual change is audited
- no destructive overwrite without history
- review-derived learning is traceable

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

### 6. Frontend Workflow Agent

Use for:
- step wizard UX
- upload/mapping/config/process/results flow
- bulk intake UI
- bank manager UI
- investigation/admin presentation

Primary modules:
- [`/Users/saraithong/Documents/bsie/frontend/src/App.tsx`](/Users/saraithong/Documents/bsie/frontend/src/App.tsx)
- [`/Users/saraithong/Documents/bsie/frontend/src/store.ts`](/Users/saraithong/Documents/bsie/frontend/src/store.ts)
- [`/Users/saraithong/Documents/bsie/frontend/src/components/steps`](/Users/saraithong/Documents/bsie/frontend/src/components/steps)
- [`/Users/saraithong/Documents/bsie/frontend/src/components/BulkIntake.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/BulkIntake.tsx)
- [`/Users/saraithong/Documents/bsie/frontend/src/components/BankManager.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/BankManager.tsx)

Success criteria:
- wizard state remains coherent
- API coupling stays centralized
- analyst review gates remain explicit

### 7. Testing / Reviewer Agent

Use for:
- regression tests
- edge-case validation
- review findings

Primary modules:
- [`/Users/saraithong/Documents/bsie/tests`](/Users/saraithong/Documents/bsie/tests)
- [`/Users/saraithong/Documents/bsie/frontend/src/components/**/*.test.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components)

Success criteria:
- changed behavior is covered
- forensic constraints are regression-tested
- findings are severity-ordered and concrete

## Preferred Subagent Roster

Use these more specific roles when the task is broad enough to justify delegation:

### API / Contract Agent

Use for:
- backend request or response contract changes
- endpoint glue changes
- compatibility adapters between UI payloads and backend services

Primary modules:
- [`/Users/saraithong/Documents/bsie/app.py`](/Users/saraithong/Documents/bsie/app.py)
- [`/Users/saraithong/Documents/bsie/persistence/schemas.py`](/Users/saraithong/Documents/bsie/persistence/schemas.py)

Forbidden overlap:
- do not share write ownership of [`/Users/saraithong/Documents/bsie/app.py`](/Users/saraithong/Documents/bsie/app.py)

### Persistence / Schema Agent

Use for:
- SQLAlchemy model changes
- raw-row, parser-run, account, transaction, or review schema work
- migration-sensitive persistence changes

Primary modules:
- [`/Users/saraithong/Documents/bsie/persistence/models.py`](/Users/saraithong/Documents/bsie/persistence/models.py)
- [`/Users/saraithong/Documents/bsie/persistence/base.py`](/Users/saraithong/Documents/bsie/persistence/base.py)
- [`/Users/saraithong/Documents/bsie/services/persistence_pipeline_service.py`](/Users/saraithong/Documents/bsie/services/persistence_pipeline_service.py)

Forbidden overlap:
- do not let a second builder edit persistence models or migrations at the same time

### Learning / Matching Agent

Use for:
- bank fingerprint memory
- mapping profile ranking
- account identity reuse
- duplicate and match heuristics

Primary modules:
- [`/Users/saraithong/Documents/bsie/core/bank_memory.py`](/Users/saraithong/Documents/bsie/core/bank_memory.py)
- [`/Users/saraithong/Documents/bsie/core/mapping_memory.py`](/Users/saraithong/Documents/bsie/core/mapping_memory.py)
- [`/Users/saraithong/Documents/bsie/services/account_resolution_service.py`](/Users/saraithong/Documents/bsie/services/account_resolution_service.py)
- [`/Users/saraithong/Documents/bsie/services/duplicate_detection_service.py`](/Users/saraithong/Documents/bsie/services/duplicate_detection_service.py)
- [`/Users/saraithong/Documents/bsie/services/transaction_matching_service.py`](/Users/saraithong/Documents/bsie/services/transaction_matching_service.py)

### Graph / Export Agent

Use for:
- graph nodes, edges, findings, and neighborhoods
- i2/anx and workbook export flows
- case analytics and graph-safe downstream formats

Primary modules:
- [`/Users/saraithong/Documents/bsie/core/graph_analysis.py`](/Users/saraithong/Documents/bsie/core/graph_analysis.py)
- [`/Users/saraithong/Documents/bsie/core/graph_export.py`](/Users/saraithong/Documents/bsie/core/graph_export.py)
- [`/Users/saraithong/Documents/bsie/services/graph_analysis_service.py`](/Users/saraithong/Documents/bsie/services/graph_analysis_service.py)
- [`/Users/saraithong/Documents/bsie/services/export_service.py`](/Users/saraithong/Documents/bsie/services/export_service.py)

### Frontend Wizard Agent

Use for:
- Step 1-5 flow
- upload/mapping/config/process/results UX
- wizard state and progress coherence

Primary modules:
- [`/Users/saraithong/Documents/bsie/frontend/src/components/steps`](/Users/saraithong/Documents/bsie/frontend/src/components/steps)
- [`/Users/saraithong/Documents/bsie/frontend/src/store.ts`](/Users/saraithong/Documents/bsie/frontend/src/store.ts)

Forbidden overlap:
- do not edit [`/Users/saraithong/Documents/bsie/frontend/src/store.ts`](/Users/saraithong/Documents/bsie/frontend/src/store.ts) concurrently with another frontend builder

### Frontend Admin Agent

Use for:
- Investigation Admin
- graph exploration UI
- bulk intake UI
- bank manager/admin flows

Primary modules:
- [`/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.tsx)
- [`/Users/saraithong/Documents/bsie/frontend/src/components/GraphExplorer.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/GraphExplorer.tsx)
- [`/Users/saraithong/Documents/bsie/frontend/src/components/BulkIntake.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/BulkIntake.tsx)
- [`/Users/saraithong/Documents/bsie/frontend/src/components/BankManager.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/BankManager.tsx)

### Documentation Agent

Use for:
- architecture docs
- subagent policy docs
- operational guidance

Primary modules:
- project markdown files

Policy:
- documentation is usually owned by the orchestrator unless the user explicitly asks for a docs-only delegated pass

## Coordination Rules

- Do not change parser semantics and persistence semantics in the same patch unless the change is fully regression-tested.
- Keep file-based exports working even when DB-backed retrieval changes.
- Review and audit changes must never mutate raw evidence rows.
- Graph export changes require tests for schema, IDs, direction, lineage, and inferred/confirmed safety.
- Account-related changes must explicitly consider:
  - digits-only normalization
  - valid lengths of exactly 10 or 12
  - Excel leading-zero loss
  - Excel scientific notation
  - preservation of the original raw value

## Standard Team Shapes

Use these default bundles before inventing a new arrangement:

### Intake + Wizard Feature

- 1 researcher for intake and contract survey
- 1 backend builder for [`/Users/saraithong/Documents/bsie/app.py`](/Users/saraithong/Documents/bsie/app.py) and intake services
- 1 frontend wizard builder for step UI changes
- 1 tester

### Review + Audit Feature

- 1 backend review builder
- 1 frontend admin builder
- 1 tester

### Learning / Memory Feature

- 1 learning builder
- 1 API integration owner
- optional 1 frontend builder only if a new analyst-facing control is needed
- 1 tester

### Graph / Export Feature

- 1 graph/export builder
- optional 1 frontend admin builder for graph UI
- 1 tester

### Platform / Admin Feature

- 1 platform builder
- optional 1 frontend admin builder
- 1 tester

## Handoff Contract For Every Subagent

Every subagent should return:

1. what it inspected
2. what it changed
3. files changed
4. tests run or still needed
5. risks or assumptions

Do not accept “done” without this handoff.

## Practical Orchestration Pattern

For most BSIE work, use this order:

1. Research the affected layer and shared files.
2. Lock ownership for shared files.
3. Implement backend/schema changes first when contracts change.
4. Implement frontend integration after backend contracts are stable.
5. Add or update regression tests.
6. Review final behavior against evidence-integrity rules.
