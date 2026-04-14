# Handoff Log

> อัพเดตทุกครั้งก่อนสลับ agent หรือจบ session
> Agent ตัวถัดไปจะอ่านไฟล์นี้เป็นอย่างแรก

## Current State

- **Last agent:** Claude Code (Opus 4.6)
- **Date:** 2026-04-15
- **Branch:** `Smarter-BSIE`

## Done (latest session)

- เพิ่ม SPNI integration router (`routers/spni.py` + `services/spni_service.py`)
  - 4 endpoints: health, runs, preview, export
  - Batched SQL queries (no N+1), typed datetime params, Query bounds
  - 16 tests ใน `tests/test_spni_api.py`
- แก้ไข `app.py` — register SPNI router + CORS localhost:3000
- แก้ไข `routers/results.py` — timeline endpoint ส่ง transaction_datetime + posted_date
- แก้ไข `routers/ingestion.py` — ลบ .csv จาก allowlist, fix HTTPException re-raise
- ลดความซับซ้อน `AccountFlowGraph.tsx` — ลบ async CSV fetch ใช้ useMemo แทน
- ปรับ `Step5Results.tsx` — ใช้ timeline data สำหรับ graph/charts
- อัพเดต docs ทั้งหมด (README, ARCHITECTURE, FEATURES, CLAUDE.md) ให้เป็นปัจจุบัน

## Next (priority order)

1. SPNI Sprint 0-2 (init project, workspace/entity CRUD, graph viz) — ที่ `/Users/saraithong/Documents/The terminal/spni/`
2. SPNI Sprint 3 — สร้าง BSIEAdapter ฝั่ง SPNI เรียก `/api/spni/export`
3. BSIE: พิจารณา Pydantic response models สำหรับ SPNI endpoints (OpenAPI docs)
4. BSIE: ADR-005 legacy table migration (v4.1-4.3)

## Active Decisions

- SPNI integration ใช้ Module Adapter Pattern — BSIE standalone, SPNI เรียกผ่าน REST API
- Export scoped by `parser_run_id` — ไม่มี workspace concept ใน BSIE
- Entity model ไม่มี `identifier_type` — SPNI adapter ต้อง derive จาก `entity_type`
- Parser run status ใช้ `"done"` (ไม่ใช่ `"completed"`)
- AccountFlowGraph ใช้ in-memory aggregation แทน CSV fetch (simpler, no async)

## Warnings

- `tests/test_app_api.py::test_upload_accepts_ofx_and_returns_identity_guess` — fail เนื่องจาก path mismatch (pre-existing, ไม่เกี่ยวกับงาน SPNI)
- BSIE server ต้องรันจาก `/Users/saraithong/Documents/The terminal/bsie/` ไม่ใช่ `/Users/saraithong/Documents/bsie/`
- CORS `localhost:3000` เพิ่มแล้ว — ถ้า SPNI เปลี่ยน port ต้องอัพเดต `app.py` line 181

---

## History

<!-- ย้าย Current State ลงมาที่นี่เมื่ออัพเดตรอบใหม่ -->
