# Handoff Log

> อัพเดตทุกครั้งก่อนสลับ agent หรือจบ session
> Agent ตัวถัดไปจะอ่านไฟล์นี้เป็นอย่างแรก

## Current State

- **Last agent:** Claude Code (Opus 4.6)
- **Date:** 2026-04-15
- **Branch:** `Smarter-BSIE`
- **Baseline:** tests green (229 passed, 1 pre-existing skip)
- **Server:** `uvicorn app:app --host 0.0.0.0 --port 8757`

## Done (latest session)

- เพิ่ม SPNI integration router (`routers/spni.py` + `services/spni_service.py`)
  - `GET /api/spni/health` — health check
  - `GET /api/spni/runs` — list completed parser runs (status="done")
  - `GET /api/spni/runs/{id}/preview` — preview counts + accounts + date range
  - `GET /api/spni/export?run_id=...` — batch export accounts + transactions + entities
  - Batched SQL queries (no N+1), typed `datetime` params, `Query(ge=, le=)` bounds
  - 16 tests ใน `tests/test_spni_api.py`
- แก้ไข `app.py` — register SPNI router + CORS `localhost:3000`
- แก้ไข `routers/results.py` — timeline endpoint ส่ง `transaction_datetime` + `posted_date`
- แก้ไข `routers/ingestion.py` — ลบ .csv จาก allowlist, fix HTTPException re-raise
- ลดความซับซ้อน `AccountFlowGraph.tsx` — ลบ async CSV fetch ใช้ `useMemo` แทน
- ปรับ `Step5Results.tsx` — ใช้ timeline data สำหรับ graph/charts
- อัพเดต docs: README v4.1, ARCHITECTURE, FEATURES, DECISIONS (3 entries)

## Commits (this session)

```
bae254f docs: update all documentation to v4.1 with SPNI integration
ea082d4 docs: add agent session protocol, handoff docs, and decision log
d035086 feat: timeline datetime fields, graph simplification, ingestion fixes
7110b36 feat: add SPNI integration router for Sprint 3 data export
```

## Next (priority order)

1. **SPNI Sprint 0-2** — init Next.js project, workspace/entity CRUD, graph viz (`/Users/saraithong/Documents/The terminal/spni/`)
2. **SPNI Sprint 3** — สร้าง BSIEAdapter ฝั่ง SPNI เรียก `/api/spni/export`
3. BSIE: พิจารณา Pydantic response models สำหรับ SPNI endpoints (OpenAPI docs)
4. BSIE: ADR-005 legacy table migration (v4.1-4.3)

## Active Decisions

- SPNI integration ใช้ Module Adapter Pattern — BSIE standalone, SPNI เรียกผ่าน REST API
- Export scoped by `parser_run_id` — ไม่มี workspace concept ใน BSIE
- Entity model ไม่มี `identifier_type` — SPNI adapter ต้อง derive จาก `entity_type`
- Parser run status ใช้ `"done"` (ไม่ใช่ `"completed"`)
- AccountFlowGraph ใช้ in-memory aggregation แทน CSV fetch

## Warnings

- `tests/test_app_api.py::test_upload_accepts_ofx_and_returns_identity_guess` — fail เนื่องจาก path mismatch (`/Users/saraithong/Documents/bsie/` vs `/Users/saraithong/Documents/The terminal/bsie/`) — pre-existing, ไม่เกี่ยวกับงานนี้
- BSIE server ต้องรันจาก `/Users/saraithong/Documents/The terminal/bsie/`
- CORS `localhost:3000` เพิ่มแล้ว — ถ้า SPNI เปลี่ยน port ต้องอัพเดต `app.py` line 181
- `CLAUDE.md` ใช้ `@AGENTS.md` (pointer) — เนื้อหาจริงอยู่ใน `AGENTS.md`

## Failed Attempts

- Claude in Chrome extension — ไม่สามารถเชื่อมต่อได้ ถอนการติดตั้งแล้ว ใช้ Control Chrome แทน

## Environment

- Python 3.12.13 (`.venv/`)
- Node (frontend): React 19 + Vite
- Database: SQLite WAL at `data/bsie.db`
- No new deps installed this session

---

## History

<!-- ย้าย Current State ลงมาที่นี่เมื่ออัพเดตรอบใหม่ -->
