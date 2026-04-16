# BSIE Subagent Checklists And Templates

> Updated for BSIE v4.1 -- `app.py` is a thin shell with 22 routers. Subagent file ownership targets individual `routers/*.py` and `services/*.py` files rather than the monolithic app.py.

This document turns the BSIE subagent policy into practical checklists and reusable templates.

Use it before spawning subagents for real work.

## 1. Pre-Spawn Checklist

Run this checklist before creating any subagent:

1. What is the real task layer?
   - intake
   - normalization
   - learning/matching
   - review/audit
   - graph/export
   - platform/admin
   - frontend wizard
   - frontend admin
   - documentation
2. Which files are the likely chokepoints?
3. Which files are shared and must have exactly one owner?
4. Is there any schema, API contract, or pipeline-order risk?
5. Can the task be split by interface or layer instead of by feature label?
6. What is the smallest team shape that can finish safely?
7. Which tests already pin current behavior?
8. Which raw values, lineage fields, audit rows, or exports must remain unchanged?

If you cannot answer these first, do research before spawning builders.

## 2. Shared-File Ownership Checklist

Before any builder starts, write a quick ownership map like this:

```md
Shared file map

- app.py -> Lifecycle / middleware owner (rarely edited)
- routers/*.py -> One owner per router (domain-specific)
- persistence/models.py -> Persistence / Schema owner
- persistence/schemas.py -> API / Contract owner
- pipeline/process_account.py -> Pipeline / Normalization owner
- frontend/src/api.ts -> Frontend integration owner
- frontend/src/store.ts -> Frontend wizard owner
- frontend/src/components/InvestigationDesk.tsx -> Frontend admin owner
- frontend/src/components/investigation/*.tsx -> Frontend admin owner
- markdown docs -> Orchestrator
```

Rules:

- non-owners may read shared files
- non-owners must not edit shared files
- if a shared file must change, route the change through the owner
- keep cross-agent integration through interfaces whenever possible

## 3. Team Shape Selector

Use this default chooser:

### Tiny change

Use:
- orchestrator only

Good for:
- one-file docs change
- isolated bug in a low-risk file

### Single-layer feature

Use:
- 1 builder
- 1 tester

Good for:
- review service tweak
- bulk UI refinement
- graph export adjustment with no API change

### Cross-layer feature with a stable contract

Use:
- 1 backend builder
- 1 frontend builder
- 1 tester

Good for:
- new analyst-facing UI using an existing endpoint
- admin workflow improvements with fixed payloads

### Contract or evidence-path feature

Use:
- 1 researcher
- 1 contract/persistence builder
- optional 1 frontend builder after contract is stable
- 1 tester

Good for:
- schema change
- upload/process contract change
- parser-run or raw-row persistence change

## 4. Subagent Brief Template

Copy and fill this before spawning a subagent:

```md
Role:
- API / Contract Agent

Objective:
- Add a safe backend adapter for remembered account names in Step 3

Allowed file scope:
- /Users/saraithong/Documents/bsie/app.py
- /Users/saraithong/Documents/bsie/persistence/schemas.py

Forbidden file scope:
- /Users/saraithong/Documents/bsie/pipeline/process_account.py
- /Users/saraithong/Documents/bsie/frontend/src/store.ts
- all markdown files

Deliverables:
- endpoint or contract update
- minimal compatibility handling
- concise summary with file references

Success criteria:
- frontend can call the new contract
- raw evidence semantics unchanged
- backward compatibility preserved unless explicitly removed
```

## 5. Research Agent Prompt Template

Use when the task is broad or risky:

```md
Read-only codebase survey. Do not edit files.

Goal:
- summarize the relevant architecture for <task>
- identify shared files and likely ownership boundaries
- call out existing tests and compatibility risks

Focus files:
- <file list>

Return:
1. what you inspected
2. shared files that should have one owner
3. likely agent split
4. tests already covering this area
5. top risks and assumptions
```

## 6. Builder Agent Prompt Template

Use when ownership is already clear:

```md
Implement only within the allowed file scope.
Do not edit forbidden files.
Do not revert unrelated changes.

Goal:
- <implementation goal>

Allowed file scope:
- <file list>

Forbidden file scope:
- <file list>

Constraints:
- preserve evidentiary integrity
- preserve backward compatibility unless the task explicitly removes it
- keep diffs minimal
- add or update tests only in your owned test scope

Return:
1. summary of changes
2. files changed
3. tests run or needed
4. risks and assumptions
```

## 7. Tester / Reviewer Prompt Template

Use after builders finish:

```md
Review the completed changes in your test scope only.
Do not broaden the feature.

Goal:
- verify behavior
- identify regressions
- call out missing tests or unsafe assumptions

Focus:
- <feature scope>

Check for:
- raw evidence preservation
- normalized vs raw field correctness
- API compatibility
- export compatibility
- audit and review safety
- account-number handling (10 or 12 digits, leading zeros, scientific notation)

Return:
1. findings ordered by severity
2. residual risks
3. tests passed, missing, or flaky
```

## 8. Final Integration Checklist

Before closing a multi-agent task, confirm:

1. shared-file ownership was respected
2. no two builders edited the same chokepoint file
3. contracts were stabilized before UI integration
4. raw evidence rows were not mutated
5. lineage and auditability remain intact
6. exports still work
7. targeted tests were updated and run
8. assumptions are documented in the final summary

## 9. BSIE-Specific Red Flags

Pause and re-evaluate if:

- two agents both want to edit [`/Users/saraithong/Documents/bsie/app.py`](/Users/saraithong/Documents/bsie/app.py)
- a task wants to change both parser semantics and persistence semantics at once
- a frontend builder wants to invent a new payload without a backend owner
- a “cleanup” removes raw values, review history, or lineage
- an account-number fix silently rewrites malformed or ambiguous source values

## 10. Recommended Default

For most BSIE work, start with this:

1. orchestrator researches locally
2. one owner for the contract path
3. one owner for the UI path only if needed
4. one tester/reviewer

BSIE usually needs careful sequencing more than maximum parallelism.
