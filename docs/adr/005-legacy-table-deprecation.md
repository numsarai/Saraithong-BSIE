# ADR-005: Legacy Table Deprecation Plan

**Status:** In Progress  
**Date:** 2026-04-12  
**Author:** ร้อยตำรวจเอกณัฐวุฒิ สาหร่ายทอง

## Context
BSIE v3.0 used SQLModel-based "legacy" tables. v4.0 introduced new SQLAlchemy models that duplicate functionality. Both coexist in the database.

## Legacy Tables (still active)

| Table | Used By | Replacement | Safe to Remove? |
|-------|---------|-------------|----------------|
| `mapping_profile` | `core/mapping_memory.py` | `mapping_profiles` (new) | ❌ Not yet — mapping memory still reads/writes |
| `bank_fingerprint` | `core/bank_memory.py` | None (unique to legacy) | ❌ Not yet — bank detection uses it |
| `job` | `tasks.py`, `database.py` | `parser_runs` (new) | ⚠️ Partially — pipeline uses both |
| `job_meta` | `tasks.py` | `parser_runs.summary_json` | ⚠️ Partially — could migrate |
| `override` | `core/override_manager.py` | ReviewDecision + Transaction.analyst_note | ❌ Not yet — override manager reads it |

## Decision
Keep legacy tables until each dependent module is migrated:
1. Migrate `mapping_memory.py` to use `mapping_profiles` table
2. Migrate `override_manager.py` to use new review system
3. Migrate `tasks.py` job tracking to use `parser_runs`
4. After migration, drop legacy tables via Alembic migration

## Timeline
- v4.1: Migrate mapping_memory + override_manager
- v4.2: Migrate tasks.py job tracking
- v4.3: Drop legacy tables
