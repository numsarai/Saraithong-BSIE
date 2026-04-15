# Handoff Log

> อัพเดตทุกครั้งก่อนสลับ agent หรือจบ session
> Agent ตัวถัดไปจะอ่านไฟล์นี้เป็นอย่างแรก

## Current State

- **Last agent:** Codex (GPT-5)
- **Date:** 2026-04-15
- **Branch:** `codex/spni-export-test-runtime-pr`
- **Baseline:** backend green (`231 passed`), frontend green (`33 passed`)
- **Server:** `uvicorn app:app --host 0.0.0.0 --port 8757`

## Done (latest session)

- ทำ session-start protocol ครบ: อ่าน `docs/HANDOFF.md`, `docs/DECISIONS.md`, ตรวจว่า `docs/.handoff-snapshot.md` ยังไม่มี, และเช็ก `git log --oneline -10`
- ตรวจ repo state เพื่อเตรียม PR:
  - ยืนยันว่า working tree สะอาด
  - ยืนยันว่า `Smarter-BSIE` ahead จาก `origin/Smarter-BSIE` อยู่ 6 commits
  - สร้าง PR branch `codex/spni-export-test-runtime-pr` จาก `HEAD` ปัจจุบันเพื่อไม่ push ตรงกลับ shared branch
- rerun baseline tests สดก่อนเปิด PR:
  - `pytest tests/` -> `231 passed`
  - `frontend npm test` -> `33 passed`
- ไม่มี product-code change ใหม่ใน session นี้; เป้าหมายของ session คือ package งานเดิมให้อยู่ในรูป branch/PR ที่ปลอดภัยและอ้างอิงผลทดสอบล่าสุดได้

## Commits (this session)

```
Pending a handoff-only commit on `codex/spni-export-test-runtime-pr` before push/PR creation.
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

- Codex (GPT-5), 2026-04-15
  - เพิ่ม canonical evidence-path self-heal ใน `services/file_ingestion_service.py`
  - แยก pytest runtime ออกจาก project-root state ใน `tests/conftest.py`
  - เก็บ frontend test warnings ใน `frontend/src/App.workflow.test.tsx` และ `frontend/src/test/setup.ts`
  - ยืนยันผล: `pytest tests/` = `231 passed`, `frontend npm test` = `33 passed`
- Claude Code (Opus 4.6), 2026-04-15
  - เพิ่ม SPNI router/service, graph/timeline ingestion fixes, และ docs v4.1
