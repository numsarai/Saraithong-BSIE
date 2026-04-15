# Handoff Log

> อัพเดตทุกครั้งก่อนสลับ agent หรือจบ session
> Agent ตัวถัดไปจะอ่านไฟล์นี้เป็นอย่างแรก

## Current State

- **Last agent:** Codex (GPT-5)
- **Date:** 2026-04-15
- **Branch:** `codex/spni-export-test-runtime-pr`
- **Baseline:** backend green (`260 passed`), frontend green (`33 passed`)
- **Server:** `uvicorn app:app --host 0.0.0.0 --port 8757`

## Done (latest session)

- ตรวจ CI failure บน PR #10 แล้วเจอ 2 ชั้น:
  - `Backend Tests` ล้มตั้งแต่ test collection เพราะ `services/report_service.py` import `from fpdf import FPDF` แต่ CI ติดตั้งจาก `requirements.txt` ซึ่งยังไม่มี `fpdf2`
  - หลัง push แก้ dependency แล้ว PR-side `CI` ผ่าน แต่ยังมี `CodeQL` fail จาก open alert `py/path-injection` ที่ `services/file_ingestion_service.py`
- แก้ dependency สำหรับ backend CI:
  - เพิ่ม `fpdf2>=2.8.0` ใน `requirements.txt`
- แก้ CodeQL path-validation สำหรับ evidence storage:
  - เพิ่ม `_normalize_file_id()` ให้รับเฉพาะ UUID
  - เปลี่ยน evidence filename จากการประกอบด้วย sanitized suffix ไปเป็น fixed allowlist mapping (`original.xlsx`, `original.ofx`, ... , fallback `original.dat`) เพื่อให้ storage path ขึ้นกับ server-controlled UUID + known-safe filename เท่านั้น
  - ทำ `_canonical_evidence_path()` / `_canonical_evidence_exists()` / `_write_canonical_evidence()` ให้ทำงานกับ `FileRecord` โดยตรง แทนการรับ path parts ดิบ
  - ปรับ duplicate repair ให้ reuse/repair เฉพาะ canonical path ใต้ current `EVIDENCE_DIR` แทนการ `resolve()` arbitrary stored path จาก record เดิม
  - คง canonical stored path/`storage_key` เดิมไว้ (`.../original.ofx` เป็นต้น) เพื่อไม่กระทบ parser dispatch และ duplicate self-heal behavior
  - ปรับ regression test ให้ validate invalid file id ผ่าน `_normalize_file_id()` โดยตรง และให้ duplicate repair ยังเทียบ resolved path ได้ถูกต้องบน macOS temp alias
- เพิ่ม regression test `test_canonical_evidence_path_rejects_invalid_file_id` ใน `tests/test_persistence_platform.py`
- ยืนยันผลหลังแก้:
  - `.venv/bin/python -m pytest tests/test_persistence_platform.py -q` -> `11 passed`
  - `.venv/bin/python -m pytest tests/ -q` -> `260 passed`
- เตรียม push latest follow-up commit นี้กลับเข้า `codex/spni-export-test-runtime-pr` เพื่ออัปเดต PR checks

## Commits (this session)

```
Pending latest follow-up commit for the fixed storage-name allowlist / record-based evidence-path fix (`services/file_ingestion_service.py`, `tests/test_persistence_platform.py`, `docs/HANDOFF.md`, `docs/DECISIONS.md`) before push.
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
- ถ้า PR ยังมี `CodeQL` fail หลัง push รอบนี้ ให้ตรวจ open code-scanning alert ใหม่บน PR merge ref; ตอนนี้ backend tests ผ่านที่ `260 passed` แล้ว เหลือยืนยันว่า CodeQL ปิด alert สองจุดเดิมได้จริง

## Failed Attempts

- ความพยายามรอบก่อนที่ใช้ regex-sanitized suffix + realpath/prefix check อย่างเดียว ยังไม่พอให้ CodeQL ปิด alert `py/path-injection`; รอบล่าสุดจึงเปลี่ยนเป็น fixed storage-name allowlist แทน dynamic suffix composition

## Environment

- Python 3.12.13 (`.venv/`)
- Node (frontend): React 19 + Vite
- Database: SQLite WAL at `bsie.db`
- No new deps installed this session

---

## History

- Codex (GPT-5), 2026-04-15
  - เปลี่ยน evidence storage ให้ใช้ fixed allowlist filename ต่อชนิดไฟล์ (`original.xlsx`, `original.ofx`, ฯลฯ) แทน dynamic suffix string
  - ปรับ helper ให้ operate บน `FileRecord` โดยตรง และยังคง canonical `stored_path`/`storage_key` เดิมเพื่อไม่กระทบ ingestion dispatch
  - ยืนยันผล: targeted persistence `11 passed`, backend suite `260 passed`
- Codex (GPT-5), 2026-04-15
  - แก้ CodeQL `py/path-injection` บน `services/file_ingestion_service.py` ด้วย UUID/suffix normalization และ canonical-path-only duplicate repair
  - refine helper ให้ validate ด้วย `realpath` แต่คืน stored path เดิมของ runtime
  - rewrite sink helpers ให้มี local `abspath/realpath + prefix check` ก่อน `exists/open`
  - align sinks ให้ใช้ validated `realpath` เดียวกัน และปรับ test ให้ assert ที่ resolved path
  - เพิ่ม regression test `test_canonical_evidence_path_rejects_invalid_file_id`
  - ยืนยันผล: targeted persistence `11 passed`, backend suite `232 passed`
- Codex (GPT-5), 2026-04-15
  - แก้ CI backend collection failure โดยเพิ่ม `fpdf2>=2.8.0` ใน `requirements.txt`
  - ยืนยัน local import `from fpdf import FPDF` และ backend suite `231 passed`
- Codex (GPT-5), 2026-04-15
  - เพิ่ม canonical evidence-path self-heal ใน `services/file_ingestion_service.py`
  - แยก pytest runtime ออกจาก project-root state ใน `tests/conftest.py`
  - เก็บ frontend test warnings ใน `frontend/src/App.workflow.test.tsx` และ `frontend/src/test/setup.ts`
  - ยืนยันผล: `pytest tests/` = `231 passed`, `frontend npm test` = `33 passed`
- Claude Code (Opus 4.6), 2026-04-15
  - เพิ่ม SPNI router/service, graph/timeline ingestion fixes, และ docs v4.1
