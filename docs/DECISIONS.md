# Decision Log

> บันทึกการตัดสินใจทางเทคนิคที่สำคัญ
> ป้องกัน agent ตัวถัดไปตัดสินใจซ้ำหรือขัดแย้ง

## Format

```
### DEC-NNN: Title
- **Date:** YYYY-MM-DD
- **Status:** accepted / superseded / deprecated
- **Context:** ทำไมต้องตัดสินใจเรื่องนี้
- **Decision:** เลือกอะไร
- **Alternatives:** ทางเลือกอื่นที่พิจารณาแล้วไม่เลือก
- **Consequences:** ผลกระทบที่ต้องรู้
```

---

### DEC-006: Reports and SPNI exports must scope metadata to the selected evidence set
- **Date:** 2026-04-16
- **Status:** accepted
- **Context:** Report generation and SPNI export now operate on persisted multi-run evidence. If alerts/accounts/entities are derived from the whole database or only the current transaction page, outputs can mix unrelated investigations or return inconsistent totals.
- **Decision:** Account reports resolve the account row from the selected `parser_run_id` when provided and only include alerts for that run; case reports only include alerts linked to the requested accounts; SPNI export derives account/entity metadata and totals from the full filtered result set before paginating transactions.
- **Alternatives:** (1) Keep loose normalized-account lookups and global alert queries — risks wrong bank/holder selection and cross-case contamination. (2) Page accounts/entities together with transactions — makes totals and metadata incomplete for paged imports.
- **Consequences:** Court-facing PDFs remain scoped to the intended evidence set, and SPNI can page through transactions without losing the full account/entity context for the filtered run.

### DEC-005: Evidence storage filenames ต้องมาจาก fixed allowlist
- **Date:** 2026-04-15
- **Status:** accepted
- **Context:** CodeQL ยังเปิด `py/path-injection` บน evidence storage แม้จะ sanitize suffix และตรวจ root prefix แล้ว เพราะ sink path ยังถูกประกอบจาก dynamic suffix string
- **Decision:** map `original_filename` ไปเป็น known-safe storage filename โดยตรง (`original.xlsx`, `original.ofx`, `original.pdf`, ... , fallback `original.dat`) และให้ evidence-path helpers ทำงานกับ `FileRecord` UUID ที่ระบบสร้างเอง
- **Alternatives:** (1) regex sanitize suffix ต่อไป — ยังไม่พอให้ CodeQL ปิด alert (2) ตัด extension ออกจาก stored path ทั้งหมด — เสี่ยงกระทบ ingestion/parser dispatch ที่ใช้นามสกุลไฟล์
- **Consequences:** stored path ยังอ่านง่ายและคง suffix ที่ parser ต้องใช้, duplicate self-heal ยังซ่อมกลับสู่ canonical path เดิมได้, และ path construction ไม่พึ่ง dynamic suffix composition อีก

### DEC-004: Pytest runtime ต้องแยกออกจาก project-root state
- **Date:** 2026-04-15
- **Status:** accepted
- **Context:** ชุดทดสอบ API/persistence เคยใช้ `bsie.db` และ writable dirs จาก project root โดยตรง ทำให้เจอ environment-coupled failure จาก legacy records และ evidence paths ของ workspace เก่า
- **Decision:** ให้ `tests/conftest.py` สร้าง temp runtime root สำหรับ pytest แล้ว patch `paths.USER_DATA_DIR`, `DB_PATH`, และ writable runtime directories ก่อน test modules import `app`
- **Alternatives:** (1) ใช้ project-root DB ต่อแล้วคอยล้าง state เอง — ยังเสี่ยงเจอข้อมูลข้ามรอบ (2) เปลี่ยน app code ให้ special-case pytest — เพิ่ม test-specific branching ใน production modules
- **Consequences:** `pytest` จะไม่แตะ `bsie.db` หรือ `data/evidence` ของ project root อีก, path-sensitive tests เสถียรขึ้น, และ `tests/test_paths.py` ต้องยืนยัน behavior ของ test harness ใหม่แทนการ assume ว่า dev runtime = project root

### DEC-003: AccountFlowGraph ใช้ in-memory aggregation แทน CSV fetch
- **Date:** 2026-04-14
- **Status:** accepted
- **Context:** AccountFlowGraph เดิมใช้ `fetchAggregatedEdges()` async fetch CSV จาก `/api/download/{account}/processed/aggregated_edges.csv` แล้ว fallback เป็น `aggregateFromRows()` — ซับซ้อนและ CSV ไม่มีข้อมูลเวลาสำหรับ hour filter
- **Decision:** ลบ async CSV fetch ทั้งหมด ใช้ `useMemo(() => aggregateFromRows(rows, account))` ตรง ๆ
- **Alternatives:** ปรับ CSV ให้มี datetime column — เพิ่มงาน pipeline, ไม่คุ้ม
- **Consequences:** ไม่ต้อง async state management, ลดโค้ด ~90 บรรทัด, hour filter ทำงานได้ถูกต้องเสมอ

### DEC-002: SPNI integration ใช้ dedicated router ไม่ใช่ existing endpoints
- **Date:** 2026-04-14
- **Status:** accepted
- **Context:** SPNI ต้องการข้อมูล accounts + transactions + entities ในครั้งเดียว แต่ BSIE endpoints ปัจจุบันกระจายอยู่ใน 5+ routers
- **Decision:** สร้าง `routers/spni.py` + `services/spni_service.py` แยกต่างหาก กับ endpoint `/api/spni/export` ที่รวมข้อมูลทั้ง 3 ประเภท
- **Alternatives:** (1) ให้ SPNI เรียกหลาย endpoints — ซับซ้อนฝั่ง adapter, consistency risk (2) เพิ่ม query param `format=spni` ใน existing endpoints — pollutes existing API
- **Consequences:** SPNI adapter เรียกแค่ endpoint เดียว, BSIE API surface เพิ่ม 4 endpoints, ต้อง maintain ทั้ง router เดิม + SPNI router

### DEC-001: ลบ .csv ออกจาก upload allowlist
- **Date:** 2026-04-14
- **Status:** accepted
- **Context:** CSV ไม่มี structure เพียงพอให้ bank_detector ทำงาน — ไม่มี headers, keywords, sheet structure ที่จะ auto-detect bank ได้
- **Decision:** ลบ `.csv` จาก `ALLOWED_EXTENSIONS` ใน `routers/ingestion.py`
- **Alternatives:** เพิ่ม CSV parser ที่ต้องให้ user ระบุ bank เอง — เพิ่มงาน UX, ไม่มี use case จริง
- **Consequences:** User ต้องแปลง CSV เป็น Excel ก่อน upload
