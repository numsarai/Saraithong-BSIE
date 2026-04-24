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

### DEC-015: Local Ollama endpoints resolve models by role
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** DEC-008 defined separate local model roles for text, vision, and fast fallback, but the runtime still had endpoint-level defaults such as `gemma4:latest` and file analysis defaults that could drift from the documented baseline.
- **Decision:** `services/llm_service.py` now owns role-based model resolution through `OLLAMA_TEXT_MODEL`, `OLLAMA_VISION_MODEL`, `OLLAMA_FAST_MODEL`, optional `OLLAMA_MAPPING_MODEL`, and `OLLAMA_DEFAULT_MODEL` fallback. Text chat/summarization/classification use the text role, image/PDF file analysis uses the vision role, and `/api/llm/status` exposes the active non-secret role config for the UI.
- **Alternatives:** (1) Keep defaults in each router/request model — simple but inconsistent and hard to audit. (2) Require users to always pass `model` — flexible but noisy and unsafe for reproducible default flows.
- **Consequences:** Local LLM behavior is easier to reproduce and benchmark. Explicit per-request models still work, but empty/default frontend requests follow the centralized self-hosted role config.

### DEC-014: Local LLM mapping assist is suggestion-only and validation-gated
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** Phase 3 introduces Local LLM help for ambiguous or incomplete mapping. Because mapping directly affects evidentiary normalization, AI output must not silently change confirmed mappings or bypass analyst gates.
- **Decision:** `/api/mapping/assist` sends only structured mapping context (bank/detection metadata, columns, sample rows, current mapping, sheet/header) to the local Ollama model and requires JSON output. The service drops invented columns, repairs debit/credit vs signed amount conflicts, validates the merged mapping, and returns `suggestion_only=true` / `auto_pass_eligible=false`. The frontend shows the suggestion and applies it only after an explicit analyst click.
- **Alternatives:** (1) Auto-apply LLM suggestions when confidence is high — faster but unsafe for evidence handling. (2) Keep LLM only in the chat tab — safer but disconnected from the mapping workflow where ambiguity appears.
- **Consequences:** LLM mapping help can reduce manual work while preserving deterministic confirmation, dry-run validation, and analyst accountability. Offline Ollama or invalid JSON fails closed and does not alter current mappings.

### DEC-013: Variant admin UI exposes staged promotion only
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** The backend promotion endpoint can move a template variant to any non-demoted trust state, but the frontend review workflow should make evidence review deliberate and easy to audit.
- **Decision:** Bank Manager exposes per-bank variant review and promotes only one step at a time: `candidate -> verified` and `verified -> trusted`. Promotion uses the current named operator from the sidebar and disables action for the default anonymous `analyst`.
- **Alternatives:** (1) Allow direct candidate-to-trusted promotion in the UI — faster but weakens reviewer discipline. (2) Hide promotion until a global review queue exists — blocks current backend lifecycle management.
- **Consequences:** Analysts can manage variants now while preserving a staged trust lifecycle; a future global queue can reuse the same API without changing the per-bank workflow.

### DEC-012: Template variant reuse is gated by workflow risk
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** Bank template variants can reduce repeated mapping work, but upload review and bulk folder processing have different risk profiles. Upload keeps an analyst in the loop before processing; bulk can process many files without per-file confirmation.
- **Decision:** Upload/redetect may use matching `candidate`, `verified`, or `trusted` Excel variants as suggestion-only mappings when bank detection is stable and the merged mapping validates. Bulk intake may apply only `trusted` Excel variants and still marks matches as `auto_pass_eligible=false`.
- **Alternatives:** (1) Allow candidate variants in bulk too — faster learning feedback but too risky for automatic multi-file processing. (2) Do not reuse variants until a full admin UI exists — safer but blocks the deterministic guarded-learning benefit already available from backend trust states.
- **Consequences:** Analyst upload can benefit from newly confirmed variants without bypassing review gates; bulk remains conservative. OCR/PDF/image mappings stay outside variant reuse until an OCR-specific evidence review policy is designed.

### DEC-011: Bank template variants are persisted separately from legacy mapping profiles
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** Phase 2 of the mapping roadmap needs shared learning without letting a single confirmation overwrite the deterministic legacy mapping profile path. Template memory needs signatures, lifecycle state, reviewer diversity, and correction tracking before it can influence future auto-pass behavior.
- **Decision:** Store shared mapping learning in `bank_template_variants` with ordered/set signatures, source type, sheet/header metadata, confirmed mapping, usage/confirmation/correction counts, reviewer list, and trust state (`candidate`, `verified`, `trusted`). `promote_shared=true` records or updates a variant, not the legacy `mapping_profile` / `bank_fingerprint` tables.
- **Alternatives:** (1) Extend the legacy `mapping_profile` table directly — faster but lacks lifecycle/audit dimensions and keeps contamination risk. (2) Delay persistence until LLM assist — blocks deterministic learning work that does not require LLM.
- **Consequences:** Existing callers must look at `variant_id` / `shared_learning` for shared mapping learning; legacy mapping profiles remain available for existing detection behavior but are no longer written by mapping confirmation promotion.

### DEC-010: Mapping confirmation no longer promotes shared memory by default
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** `/api/mapping/confirm` previously validated lightly and immediately wrote confirmed mappings into shared mapping/bank memory. That conflicted with the guarded variant direction in DEC-009 because a single analyst confirmation could contaminate future suggestions.
- **Decision:** Mapping confirmation now validates and audits the mapping for the current run by default, runs a dry-run sample preview, and only promotes shared mapping/bank memory when `promote_shared=true` and a named reviewer is supplied. Invalid mappings are rejected before any learning write.
- **Alternatives:** (1) Keep automatic profile writes and add variants later — leaves the contamination risk active during Phase 1. (2) Disable all audit/feedback for confirmation — safer for shared memory but loses evidentiary review trail.
- **Consequences:** Frontend confirm flow must call preview/confirm with sample rows; shared profile promotion is opt-in until template variants are implemented; existing callers expecting `profile_id` on every confirmation must handle `null`.

### DEC-009: Mapping and template learning will use guarded shared variants
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** BSIE ต้องรองรับ Excel bank statements หลายรูปแบบ รวมถึงธนาคารเดิมที่เปลี่ยน header, sheet, หรือ layout บ่อย การให้ผู้ใช้ยืนยัน mapping ได้เป็นสิ่งจำเป็น แต่ถ้า save เป็น shared template ทันทีจะเสี่ยงทำให้ระบบเรียนรู้ผิดและกระทบทุกคน
- **Decision:** ผู้ใช้ทุกคนยืนยัน mapping สำหรับรอบงานปัจจุบันได้ แต่การเรียนรู้แบบ shared ต้องผ่านแนวคิด `bank template variants` และ state การโปรโมต (`candidate` → `verified` → `trusted`) โดย template ใหม่จะไม่ auto-pass และ auto-pass เปิดได้เฉพาะ trusted Excel variants เท่านั้น
- **Alternatives:** (1) ให้ทุก confirmation เขียนทับ shared template ตรง ๆ — เสี่ยง contamination สูง (2) ปิด shared learning ไปเลย — ลดความเสี่ยงแต่ทำให้ระบบไม่พัฒนาและเพิ่มงาน manual ซ้ำ
- **Consequences:** ระบบยังเรียนรู้ข้ามผู้ใช้ได้ แต่มี guardrail; ingestion flow, persistence, review gate, และ promotion logic ต้องรองรับ variant lifecycle อย่างชัดเจน

### DEC-008: Local LLM baseline on the current Mac should separate text and vision roles
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** BSIE ต้องใช้ Local LLM กับทั้งงานข้อความ/JSON/mapping reasoning และงานเอกสาร/ภาพ การใช้โมเดลเดียวครอบทุกอย่างบน MacBook Pro 16" M2 Max RAM 32GB จะไม่คุ้มที่สุดทั้งด้าน latency และคุณภาพ
- **Decision:** ใช้ baseline model แยกบทบาท: `qwen2.5:14b` สำหรับ text reasoning / Thai + JSON / mapping assist, `qwen2.5vl:7b` สำหรับ PDF/image/document understanding, และ `gemma4:e4b` เป็น fast fallback; หลีกเลี่ยง `:latest` ใน production-like flows เพื่อคง reproducibility
- **Alternatives:** (1) ใช้โมเดลเดียวกับทุก use case — ง่ายแต่ไม่ optimize (2) ใช้ reasoning model ใหม่กว่าอย่างเดียว — อาจแรงขึ้นบางงานแต่ context/tooling fit ไม่ดีเท่าในงาน Excel + structured outputs
- **Consequences:** runtime config ควรแยก text/vision models, LLM service ควรรับ env ใหม่, และ benchmark บนเครื่องจริงควรทำก่อนเปิดใช้กว้าง

### DEC-007: Runtime defaults back to local-only development
- **Date:** 2026-04-23
- **Status:** accepted
- **Context:** มี cloud demo integration แบบ Vercel + Fly.io + Supabase ค้างอยู่ใน working tree แต่รอบงานปัจจุบันต้องกลับไปพัฒนาและทดสอบแบบ local-only ก่อน เพื่อลด dependency ภายนอกและไม่ให้ runtime เผลอชี้ไปที่บริการจริง
- **Decision:** ถอด Supabase auth / external Postgres / Vercel-Fly deployment configs ออกจาก repo worktree และคืน runtime ไปเป็น local SQLite + local JWT auth ตามค่าเริ่มต้น
- **Alternatives:** (1) เก็บ cloud code ไว้หลัง env flag ต่อไป — ยังเสี่ยงเผลอผูกกับ service ภายนอกและทำให้ handoff สับสน (2) commit cloud demo แยกไว้ก่อนแล้วค่อยถอด — ไม่ตรงกับเป้าหมาย local-first ของรอบนี้
- **Consequences:** เส้นทาง dev กลับมาง่ายและ reproducible บนเครื่อง local; ถ้าจะกลับไป deploy cloud อีกครั้งควรทำเป็นงานใหม่บน branch/plan ที่ชัดเจน

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
