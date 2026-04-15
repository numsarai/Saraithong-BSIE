# Handoff Log

> อัพเดตทุกครั้งก่อนสลับ agent หรือจบ session
> Agent ตัวถัดไปจะอ่านไฟล์นี้เป็นอย่างแรก

## Current State

- **Last agent:** Codex (GPT-5)
- **Date:** 2026-04-15
- **Branch:** `Smarter-BSIE`
- **Baseline:** backend green (`231 passed`), frontend green (`33 passed`)
- **Server:** `uvicorn app:app --host 0.0.0.0 --port 8757`

## Done (latest session)

- ทำ session-start protocol ครบ: อ่าน `docs/HANDOFF.md`, `docs/DECISIONS.md`, เช็ก `git log --oneline -10`, ยืนยันว่า `docs/.handoff-snapshot.md` ยังไม่มี
- แก้ `services/file_ingestion_service.py`
  - เพิ่ม canonical evidence-path helper
  - เพิ่ม self-heal สำหรับ duplicate uploads: ถ้า `stored_path` หายหรืออยู่นอก `EVIDENCE_DIR` ปัจจุบัน ให้ rewrite evidence file เข้า path ปัจจุบันและอัปเดต `stored_path` / `storage_key`
- เพิ่ม regression test `test_persist_upload_repairs_missing_duplicate_evidence_path` ใน `tests/test_persistence_platform.py`
- แยก pytest runtime ออกจาก project root:
  - แก้ `tests/conftest.py` ให้สร้าง temp runtime root แล้ว patch `paths.USER_DATA_DIR`, `DB_PATH`, และ writable dirs ก่อน test modules import `app`
  - ปรับ `tests/test_paths.py` ให้ตรวจ behavior ของ isolated test runtime แทนการ assume ว่า `USER_DATA_DIR == BUNDLE_DIR`
- เก็บ frontend test warning:
  - แก้ `frontend/src/App.workflow.test.tsx` ให้ mock `LlmChat` ออกจาก workflow test ที่ไม่ได้ทดสอบ chat
  - ห่อ `useStore` resets ใน `act(...)` เพื่อไม่ให้ mounted components (`Sidebar`, `App`, `Step3Config`) อัปเดตนอก React test boundary
  - ลบการ suppress `console.error` สำหรับ `not wrapped in act`
  - แก้ `frontend/src/test/setup.ts` ให้ inject in-memory `localStorage` / `sessionStorage` stub ก่อน import `i18n` เพื่อกัน Node 25 global storage warning (`--localstorage-file`)
- ยืนยันผลหลังแก้:
  - `tests/test_paths.py` -> ผ่าน
  - `tests/test_app_api.py -k "upload_accepts_ofx or upload_uses_uploaded_by_form_field"` -> ผ่าน
  - `tests/test_persistence_platform.py -k persist_upload` -> ผ่าน
  - `pytest tests/` -> `231 passed`
  - `frontend npm test` -> `33 passed`

## Commits (this session)

```
See `git log --oneline -5` after session close for the final commit covering:
- duplicate evidence-path self-heal
- pytest runtime isolation
- frontend test warning cleanup
```

## Next (priority order)

1. **SPNI Sprint 0-2** — init Next.js project, workspace/entity CRUD, graph viz (`/Users/saraithong/Documents/The terminal/spni/`)
2. **SPNI Sprint 3** — สร้าง BSIEAdapter ฝั่ง SPNI เรียก `/api/spni/export`
3. BSIE: พิจารณา per-test DB cleanup หรือ dedicated fixtures สำหรับ tests ที่ยังพึ่ง shared in-session state
4. BSIE: พิจารณา Pydantic response models สำหรับ SPNI endpoints (OpenAPI docs)
5. BSIE: ADR-005 legacy table migration (v4.1-4.3)

## Active Decisions

- SPNI integration ใช้ Module Adapter Pattern — BSIE standalone, SPNI เรียกผ่าน REST API
- Export scoped by `parser_run_id` — ไม่มี workspace concept ใน BSIE
- Entity model ไม่มี `identifier_type` — SPNI adapter ต้อง derive จาก `entity_type`
- Parser run status ใช้ `"done"` (ไม่ใช่ `"completed"`)
- AccountFlowGraph ใช้ in-memory aggregation แทน CSV fetch
- Duplicate file reuse ต้อง self-heal `stored_path` กลับเข้า `EVIDENCE_DIR` ปัจจุบันเมื่อ path เก่าหายหรืออยู่นอก workspace ปัจจุบัน
- Pytest ต้องใช้ temp runtime root ผ่าน `tests/conftest.py` แทน project-root `bsie.db` และ writable dirs

## Warnings

- Runtime app ปกติยังใช้ `bsie.db` ที่ project root (ไม่ใช่ `data/bsie.db`)
- Pytest runtime ถูกแยกแล้ว แต่ยังเป็น session-level temp DB ไม่ใช่ per-test DB isolation
- BSIE server ต้องรันจาก `/Users/saraithong/Documents/The terminal/bsie/`
- CORS `localhost:3000` เพิ่มแล้ว — ถ้า SPNI เปลี่ยน port ต้องอัพเดต `app.py` line 181
- `CLAUDE.md` ใช้ `@AGENTS.md` (pointer) — เนื้อหาจริงอยู่ใน `AGENTS.md`
- `docs/.handoff-snapshot.md` ยังไม่มีไฟล์
- `frontend npm test` ไม่มี React `act(...)` warning และไม่มี Node `--localstorage-file` warning แล้ว

## Failed Attempts

- ไม่มี failed attempt ใหม่ใน session นี้

## Environment

- Python 3.12.13 (`.venv/`)
- Node (frontend): React 19 + Vite
- Database: SQLite WAL at `bsie.db`
- No new deps installed this session

---

## History

- Claude Code (Opus 4.6), 2026-04-15
  - เพิ่ม SPNI router/service, graph/timeline ingestion fixes, และ docs v4.1
