# BSIE Agent Orchestration

> Updated for BSIE v4.0 -- `app.py` is now ~230 lines with 21 routers under `routers/`. Subagent ownership targets individual router and service files, not a monolithic app.py.

This document explains how to split BSIE work across subagents without damaging evidence integrity or creating merge conflicts.

## Goals

Use subagents to increase speed and coverage while keeping:

- forensic traceability
- clear file ownership
- minimal merge conflict risk
- deterministic behavior across pipeline, review, and export layers

## Default Rule

Research first. Then assign builders. Then validate with tests. Do not let multiple builders edit the same shared file unless there is no safer option.

## Current BSIE Chokepoints

The current repository shape matters more than generic agent theory:

- `app.py` is now a thin lifecycle/middleware/router-registration shell (~230 lines).
- **21 routers** under `routers/` own all endpoint logic (ingestion, graph, review, alerts, auth, etc.).
- [`/Users/saraithong/Documents/bsie/pipeline/process_account.py`](/Users/saraithong/Documents/bsie/pipeline/process_account.py) is the sequential normalization/export spine.
- [`/Users/saraithong/Documents/bsie/services/persistence_pipeline_service.py`](/Users/saraithong/Documents/bsie/services/persistence_pipeline_service.py) is the evidence-to-database contract layer.
- [`/Users/saraithong/Documents/bsie/frontend/src/api.ts`](/Users/saraithong/Documents/bsie/frontend/src/api.ts) and [`/Users/saraithong/Documents/bsie/frontend/src/store.ts`](/Users/saraithong/Documents/bsie/frontend/src/store.ts) are the frontend integration chokepoints.
- `frontend/src/components/InvestigationDesk.tsx` is the largest shared admin surface, with sub-components extracted to `components/investigation/`.
- `frontend/src/components/LinkChart.tsx` replaces the former GraphExplorer for interactive graph visualization.

This means BSIE benefits from a small number of focused subagents, not a swarm.

For reusable pre-spawn checklists and fill-in prompt templates, use [`/Users/saraithong/Documents/bsie/docs/architecture/subagent-checklists.md`](/Users/saraithong/Documents/bsie/docs/architecture/subagent-checklists.md).

## Shared Files To Treat Carefully

These files are common integration points and should usually have one editor only:

- `app.py` (lifecycle only -- routers own endpoints)
- `routers/*.py` (each router is a shared file within its domain)
- `persistence/models.py`
- `persistence/schemas.py`
- `pipeline/process_account.py`
- `frontend/src/api.ts`
- `frontend/src/store.ts`
- `frontend/src/components/InvestigationDesk.tsx`

## Recommended Orchestration Sequence

1. Inspect the codebase and identify the real layer touched by the request.
2. List shared files and assign a single owner for each.
3. Spawn research agents first if the task is broad or risky.
4. Spawn builders only after interfaces and ownership are clear.
5. Keep tests in a separate scope when possible.
6. Finish with a reviewer pass and targeted regression tests.

## Concurrency Budget

Use this as the default concurrency policy:

| Task Type | Recommended Shape |
|-----------|-------------------|
| docs-only or one-file fix | orchestrator only |
| single-layer feature | 1 builder + 1 tester |
| cross-layer feature with stable contract | 1 backend builder + 1 frontend builder + 1 tester |
| schema/pipeline/evidence contract change | 1 researcher + 1 builder + 1 tester |
| graph/export feature | 1 graph/export builder + optional 1 admin UI builder + 1 tester |

For BSIE, more than 4 active agents is usually wasteful unless the user explicitly wants broad parallelization.

## Useful BSIE Agent Patterns

### Intake Change

Use when a task affects upload, mapping confirm, parser-run creation, or file evidence storage.

- Researcher scope:
  - [`/Users/saraithong/Documents/bsie/app.py`](/Users/saraithong/Documents/bsie/app.py)
  - [`/Users/saraithong/Documents/bsie/services/file_ingestion_service.py`](/Users/saraithong/Documents/bsie/services/file_ingestion_service.py)
  - [`/Users/saraithong/Documents/bsie/services/persistence_pipeline_service.py`](/Users/saraithong/Documents/bsie/services/persistence_pipeline_service.py)
- Builder scope:
  - same modules
- Test scope:
  - [`/Users/saraithong/Documents/bsie/tests/test_app_api.py`](/Users/saraithong/Documents/bsie/tests/test_app_api.py)
  - [`/Users/saraithong/Documents/bsie/tests/test_persistence_platform.py`](/Users/saraithong/Documents/bsie/tests/test_persistence_platform.py)

### Mapping And Learning Change

Use when the task affects bank detection memory, mapping profiles, remembered names, or learning feedback.

- Builder scope:
  - [`/Users/saraithong/Documents/bsie/core/bank_memory.py`](/Users/saraithong/Documents/bsie/core/bank_memory.py)
  - [`/Users/saraithong/Documents/bsie/core/mapping_memory.py`](/Users/saraithong/Documents/bsie/core/mapping_memory.py)
  - [`/Users/saraithong/Documents/bsie/services/account_resolution_service.py`](/Users/saraithong/Documents/bsie/services/account_resolution_service.py)
- Integration owner:
  - [`/Users/saraithong/Documents/bsie/app.py`](/Users/saraithong/Documents/bsie/app.py)
  - [`/Users/saraithong/Documents/bsie/frontend/src/api.ts`](/Users/saraithong/Documents/bsie/frontend/src/api.ts)
- Test scope:
  - [`/Users/saraithong/Documents/bsie/tests/test_bank_memory.py`](/Users/saraithong/Documents/bsie/tests/test_bank_memory.py)
  - [`/Users/saraithong/Documents/bsie/tests/test_mapping_memory.py`](/Users/saraithong/Documents/bsie/tests/test_mapping_memory.py)

### Review And Audit Change

Use when the task affects duplicate review, match review, transaction/account correction, or learning feedback visibility.

- Backend owner:
  - [`/Users/saraithong/Documents/bsie/services/review_service.py`](/Users/saraithong/Documents/bsie/services/review_service.py)
  - [`/Users/saraithong/Documents/bsie/services/audit_service.py`](/Users/saraithong/Documents/bsie/services/audit_service.py)
- Frontend owner:
  - [`/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.tsx)
- Test scope:
  - [`/Users/saraithong/Documents/bsie/tests/test_persistence_platform.py`](/Users/saraithong/Documents/bsie/tests/test_persistence_platform.py)
  - [`/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.test.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.test.tsx)

### Platform Change

Use when the task affects runtime source, backups, reset/restore, or desktop packaging.

- Builder scope:
  - [`/Users/saraithong/Documents/bsie/persistence/base.py`](/Users/saraithong/Documents/bsie/persistence/base.py)
  - [`/Users/saraithong/Documents/bsie/services/admin_service.py`](/Users/saraithong/Documents/bsie/services/admin_service.py)
  - [`/Users/saraithong/Documents/bsie/main_launcher.py`](/Users/saraithong/Documents/bsie/main_launcher.py)
- Test scope:
  - admin/platform tests

## Preferred Subagent Families

These role families match the current codebase more closely than generic “backend/frontend” splits:

### API / Contract

Owns:
- [`/Users/saraithong/Documents/bsie/app.py`](/Users/saraithong/Documents/bsie/app.py)
- [`/Users/saraithong/Documents/bsie/persistence/schemas.py`](/Users/saraithong/Documents/bsie/persistence/schemas.py)

Use when:
- request/response payloads change
- a frontend flow needs a backend adapter
- compatibility logic is required

### Persistence / Schema

Owns:
- [`/Users/saraithong/Documents/bsie/persistence/models.py`](/Users/saraithong/Documents/bsie/persistence/models.py)
- [`/Users/saraithong/Documents/bsie/services/persistence_pipeline_service.py`](/Users/saraithong/Documents/bsie/services/persistence_pipeline_service.py)
- Alembic or related migration files

Use when:
- evidence contract changes
- review/export storage changes
- migrations are involved

### Pipeline / Normalization

Owns:
- [`/Users/saraithong/Documents/bsie/pipeline/process_account.py`](/Users/saraithong/Documents/bsie/pipeline/process_account.py)
- normalization, reconciliation, subject inference, OFX, and classification helpers in `core/`

Use when:
- ingestion semantics or normalization rules change
- raw vs normalized handling must be preserved carefully

### Learning / Matching

Owns:
- bank memory
- mapping memory
- account identity reuse
- duplicate and transaction matching heuristics

Use when:
- the system should become more accurate over repeated use
- analyst confirmations need to reinforce reusable memory

### Review / Audit

Owns:
- [`/Users/saraithong/Documents/bsie/services/review_service.py`](/Users/saraithong/Documents/bsie/services/review_service.py)
- [`/Users/saraithong/Documents/bsie/services/audit_service.py`](/Users/saraithong/Documents/bsie/services/audit_service.py)
- [`/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.tsx) when the change is review-centric

Use when:
- manual corrections
- duplicate/match review
- audit visibility
- learning-feedback inspection

### Frontend Wizard

Owns:
- step components under [`/Users/saraithong/Documents/bsie/frontend/src/components/steps`](/Users/saraithong/Documents/bsie/frontend/src/components/steps)
- [`/Users/saraithong/Documents/bsie/frontend/src/store.ts`](/Users/saraithong/Documents/bsie/frontend/src/store.ts) when wizard state changes

Use when:
- upload → process flow changes
- review gates or wizard state changes

### Frontend Admin

Owns:
- Investigation admin
- graph explorer UI
- bulk intake UI
- bank manager UI

Use when:
- work is mostly in analyst/admin surfaces rather than the main wizard

### Graph / Export

Owns:
- graph analysis, findings, neighborhoods, Neo4j sync
- graph export, i2/anx, workbook outputs

Use when:
- downstream investigation exports or relationship analysis are changing

### Documentation

Owns:
- markdown documentation

Use when:
- the request changes project guidance, architecture docs, or subagent policy

For BSIE, the orchestrator should usually own documentation directly.

## Research Questions Worth Asking First

Before editing, subagents should answer questions like:

- Where is the evidence-preserving source of truth for this feature?
- Which file currently owns the API contract?
- Which data is raw and which data is normalized?
- Which fields are exported downstream and must remain compatible?
- Which tests already pin the current behavior?
- Which chokepoint file would create the most merge risk if two agents touched it?
- Can this task be split by interface instead of by feature label?

## Do Not Do This

- Do not let two builders edit the same router file at the same time.
- Do not let two builders edit `pipeline/process_account.py` at the same time.
- Do not let two frontend builders edit `frontend/src/store.ts` or `frontend/src/api.ts` concurrently.
- Do not let review-related changes mutate raw evidence rows.
- Do not let a frontend builder invent a new API contract without a backend owner.
- Do not let a schema change land without updating tests that prove compatibility.
- Do not “fix” malformed account numbers by silently inventing digits.

## When Not To Use Subagents

Avoid spawning subagents when:

- the request is a tiny doc edit
- the request is confined to one low-risk file
- the next step is blocked on a single urgent inspection you can do faster locally
- the likely write target is a single chokepoint file and parallel work would only increase conflict risk

BSIE rewards careful sequencing more than aggressive fan-out.

## Expected Handoff From A Subagent

Every subagent should return:

1. summary of what it inspected
2. exact files changed
3. any contract assumptions
4. tests added or needed
5. open risks

This keeps the orchestrator in control of final integration and evidence-integrity review.

## Practical Starting Point

If you want a fast default:

1. copy the pre-spawn checklist
2. write a shared-file map
3. pick a team shape from the concurrency table
4. fill in the subagent brief template
5. only then spawn builders

## Documentation Ownership

Project markdown files should usually be edited by the orchestrator only, after research is complete. This keeps the written architecture aligned with the actual codebase and avoids documentation conflicts across subagents.
