# BSIE Agents

> Updated for BSIE v4.0

This file defines the practical agent roles and orchestration rules for working inside BSIE.

## Core Principle

All agents must preserve evidentiary integrity first. Raw source values, lineage, audit logs, review history, and reproducible exports are not optional.

## Current Project Reality (v4.0)

BSIE v4.0 has been restructured from a monolithic `app.py` into a modular router architecture:

- `app.py` is now ~230 lines handling lifecycle, middleware, and router registration only.
- **21 API routers** under `routers/` own all endpoint logic: admin, alerts, analytics, annotations, auth, banks, bulk, case_tags, dashboard, exports, fund_flow, graph, ingestion, jobs, overrides, reports, results, review, search, ui, workspace.
- **34 services** under `services/` encapsulate business logic.
- `pipeline/process_account.py` remains the sequential 14-step evidence-sensitive pipeline core.
- `persistence/models.py` and `persistence/schemas.py` define the persistent evidence contract.
- `frontend/src/api.ts` and `frontend/src/store.ts` are the frontend coupling and state chokepoints.
- `InvestigationDesk.tsx` delegates to sub-components: `DatabaseTab`, `AlertsTab`, `CrossAccountTab` under `components/investigation/`.
- `LinkChart.tsx` replaces the former `GraphExplorer.tsx` for interactive graph visualization.

Subagent policy should optimize around routers and services, not around a single `app.py`.

## Before Creating Subagents

1. Inspect the task and identify which layer it touches:
   - intake
   - normalization
   - intelligence (alerts, threat hunting, SNA)
   - review
   - platform
   - frontend workflow
2. Identify which router and service files are involved.
3. Give each shared file one owner only.
4. Let non-owners read shared files, but route edits through the owner.
5. Do research before risky implementation.

Use the reusable checklist and prompt templates in `docs/architecture/subagent-checklists.md`.

## Shared File Ownership Defaults

Use these defaults unless the task clearly needs something else:

- App lifecycle owner:
  - `app.py`
- Router owners (one per router file):
  - `routers/*.py` -- each router owned by its functional domain agent
- Schema owner:
  - `persistence/models.py`
  - `persistence/schemas.py`
- Pipeline owner:
  - `pipeline/process_account.py`
- Frontend integration owner:
  - `frontend/src/api.ts`
  - `frontend/src/store.ts`
- Investigation UI owner:
  - `frontend/src/components/InvestigationDesk.tsx`
  - `frontend/src/components/investigation/*.tsx`
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
2. map shared files (routers, services, persistence)
3. assign a single owner per shared file
4. choose the smallest safe team shape
5. stabilize contracts before UI work
6. reserve testing as a separate scope when possible

The fill-in templates live in `docs/architecture/subagent-checklists.md`.

## Primary Agents

### 1. Intake Agent

Use for:
- upload flow
- file hashing and metadata verification
- bank detection
- column mapping confirmation
- parser run creation

Primary modules:
- `routers/ingestion.py`
- `routers/bulk.py`
- `services/file_ingestion_service.py`
- `services/file_metadata_service.py`
- `services/persistence_pipeline_service.py`

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
- `pipeline/process_account.py`
- `core/normalizer.py`
- `core/reconciliation.py`
- `core/ofx_io.py`
- `services/normalization_service.py`
- `services/classification_service.py`

Success criteria:
- normalized transactions persisted
- raw lineage preserved
- output package still produced

### 3. Intelligence Agent

Use for:
- duplicate detection
- account resolution
- transaction matching
- alert generation (7 rules)
- threat hunting (5 patterns)
- SNA analysis
- graph preparation

Primary modules:
- `services/alert_service.py`
- `services/anomaly_detection_service.py`
- `services/threat_hunting_service.py`
- `services/sna_service.py`
- `services/account_resolution_service.py`
- `services/duplicate_detection_service.py`
- `services/bulk_matching_service.py`
- `core/graph_export.py`
- `core/graph_analysis.py`

Success criteria:
- duplicates remain additive
- inferred matches stay reversible
- graph output is stable and i2-safe
- alerts are traceable to source findings

### 4. Review Agent

Use for:
- duplicate review
- match review
- transaction correction
- account correction
- audit inspection

Primary modules:
- `routers/review.py`
- `services/review_service.py`
- `services/audit_service.py`
- `frontend/src/components/InvestigationDesk.tsx`

Success criteria:
- every manual change is audited
- no destructive overwrite without history
- review-derived learning is traceable

### 5. Platform Agent

Use for:
- database runtime
- backup/reset/restore
- scheduled backup policy
- authentication and user management
- job queue management

Primary modules:
- `routers/admin.py`
- `routers/auth.py`
- `routers/jobs.py`
- `persistence/base.py`
- `services/admin_service.py`
- `services/auth_service.py`
- `services/job_queue_service.py`

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
- investigation workspace

Primary modules:
- `frontend/src/App.tsx`
- `frontend/src/store.ts`
- `frontend/src/components/steps/`
- `frontend/src/components/BulkIntake.tsx`
- `frontend/src/components/BankManager.tsx`
- `frontend/src/components/Dashboard.tsx`
- `frontend/src/components/investigation/`

Success criteria:
- wizard state remains coherent
- API coupling stays centralized in `api.ts`
- analyst review gates remain explicit
- i18n keys used for all labels

### 7. Testing / Reviewer Agent

Use for:
- regression tests
- edge-case validation
- review findings

Primary modules:
- `tests/`
- `frontend/src/components/**/*.test.tsx`

Success criteria:
- changed behavior is covered
- forensic constraints are regression-tested
- findings are severity-ordered and concrete

## Preferred Subagent Roster

Use these more specific roles when the task is broad enough to justify delegation:

### API / Router Agent

Use for:
- backend request or response contract changes
- endpoint additions or modifications
- compatibility adapters between UI payloads and backend services

Primary modules:
- relevant `routers/*.py` file(s)
- `persistence/schemas.py`

Forbidden overlap:
- do not let two agents edit the same router file

### Graph / Export Agent

Use for:
- graph nodes, edges, findings, and neighborhoods
- i2/anx and workbook export flows
- case analytics and graph-safe downstream formats
- fund flow analysis
- report generation

Primary modules:
- `routers/graph.py`
- `routers/exports.py`
- `routers/reports.py`
- `routers/fund_flow.py`
- `core/graph_analysis.py`
- `core/graph_export.py`
- `services/graph_analysis_service.py`
- `services/export_service.py`
- `services/fund_flow_service.py`
- `services/report_service.py`

### Frontend Investigation Agent

Use for:
- Investigation workspace tabs
- Link chart and graph exploration UI
- Alert dashboard
- Cross-account analysis UI

Primary modules:
- `frontend/src/components/InvestigationDesk.tsx`
- `frontend/src/components/investigation/*.tsx`
- `frontend/src/components/LinkChart.tsx`
- `frontend/src/components/AccountFlowGraph.tsx`
- `frontend/src/components/TimelineChart.tsx`

### Documentation Agent

Use for:
- architecture docs
- subagent policy docs
- operational guidance

Policy:
- documentation is usually owned by the orchestrator unless the user explicitly asks for a docs-only delegated pass

## Coordination Rules

- Do not change parser semantics and persistence semantics in the same patch unless the change is fully regression-tested.
- Keep file-based exports working even when DB-backed retrieval changes.
- Review and audit changes must never mutate raw evidence rows.
- Graph export changes require tests for schema, IDs, direction, lineage, and inferred/confirmed safety.
- Router changes should stay within their functional scope; cross-router logic belongs in services.
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
- 1 backend builder for ingestion router and intake services
- 1 frontend wizard builder for step UI changes
- 1 tester

### Alert / Intelligence Feature

- 1 backend builder for alert/threat services and routers
- 1 frontend admin builder for alert UI
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

Do not accept "done" without this handoff.

## Practical Orchestration Pattern

For most BSIE work, use this order:

1. Research the affected layer, routers, and services.
2. Lock ownership for shared files.
3. Implement backend/schema changes first when contracts change.
4. Implement frontend integration after backend contracts are stable.
5. Add or update regression tests.
6. Review final behavior against evidence-integrity rules.

## Agent Session Protocol

### On Session Start (MANDATORY)

1. Read `docs/HANDOFF.md` — understand current state, warnings, and pending work
2. Read `docs/DECISIONS.md` — know what was already decided (do NOT reverse without asking)
3. Check `docs/.handoff-snapshot.md` if exists — environment and test state from last session
4. Run `git log --oneline -10` — understand recent changes
5. Run tests before making changes — confirm baseline is green

### On Session End (MANDATORY)

Before ending your session, you MUST update `docs/HANDOFF.md` with:

1. **What you did** — files changed, features added/fixed, tests written
2. **What's next** — prioritized list of remaining work
3. **Decisions made** — any architectural or technical choices (also add to `docs/DECISIONS.md` if significant)
4. **Warnings** — things that are broken, unstable, or must not be touched
5. **Failed attempts** — approaches you tried that didn't work and why (saves the next agent from repeating)
6. **Environment changes** — new deps installed, migrations run, config changed

This is NON-NEGOTIABLE. The next agent (which may be a different AI) depends on this information.
