# Handoff Log

> อัพเดตทุกครั้งก่อนสลับ agent หรือจบ session
> Agent ตัวถัดไปจะอ่านไฟล์นี้เป็นอย่างแรก

## Current State

- **Last agent:** Codex (GPT-5)
- **Date:** 2026-04-24
- **Branch:** `Smarter-BSIE`
- **Runtime mode:** local-only อีกครั้ง
- **Baseline:** backend `331 passed`, frontend `34 passed`, frontend build passed
- **Auth/DB:** local JWT auth + local SQLite WAL (`bsie.db`)
- **Cloud status:** repo ไม่ผูกกับ Vercel, Fly.io, หรือ Supabase แล้วใน working tree ปัจจุบัน

## Done (latest session) — Phase 2 Gated Variant Suggestions

### What I changed
- Wired guarded bank template variants into upload and bulk mapping suggestion paths.
- Added `find_matching_template_variant(...)` lookup support with explicit trust-state filtering.
- Upload/redetect flow now:
  - checks variants only for stable Excel bank detection (`confidence >= 0.75`, non-ambiguous, non-generic)
  - allows `candidate` / `verified` / `trusted` variants as suggestion-only matches
  - validates the merged mapping before exposing it
  - returns `template_variant_match` and `suggestion_source`
- Bulk folder intake now:
  - uses the same deterministic repair/validation path
  - applies template variants only when they are `trusted`
  - keeps `auto_pass_eligible=false`; this is still suggestion/mapping selection, not evidence auto-pass
  - records `suggestion_source` and `template_variant_match` in per-file summary rows and case manifest accounts
- Frontend Step 2 now stores and displays template variant memory matches so analysts can see when a suggestion came from guarded shared learning.
- Fixed `repair_suggested_mapping` so debit/credit mappings are not later overwritten by an auto-filled signed amount column.

### Files changed
- `services/template_variant_service.py`
- `routers/ingestion.py`
- `core/bulk_processor.py`
- `utils/app_helpers.py`
- `frontend/src/store.ts`
- `frontend/src/components/steps/Step2Map.tsx`
- `frontend/src/components/steps/Step2Map.test.tsx`
- `tests/test_template_variant_service.py`
- `tests/test_app_api.py`
- `tests/test_bulk_processor.py`
- `docs/DECISIONS.md`
- `docs/HANDOFF.md`
- `docs/LOCAL_LLM_MAPPING_ROADMAP.md`

### Tests run
- Baseline before changes:
  - `.venv/bin/python -m pytest tests/ -q` -> `327 passed`
  - `npm test` in `frontend/` -> `33 passed`
- Focused after changes:
  - `.venv/bin/python -m pytest tests/test_template_variant_service.py tests/test_bulk_processor.py tests/test_app_api.py -q` -> `51 passed`
  - `npm test -- --run src/components/steps/Step2Map.test.tsx` -> `6 passed`
- Final verification:
  - `.venv/bin/python -m pytest tests/ -q` -> `331 passed`
  - `npm test` in `frontend/` -> `34 passed`
  - `npm run build` in `frontend/` -> passed, Vite large chunk warning only

### Decisions made
- Added `DEC-012`: variant suggestion reuse is gated differently for analyst upload vs bulk auto-processing.
- Upload may surface candidate variants as visible suggestions because analyst review remains in the loop.
- Bulk may apply only `trusted` variants because it processes files without per-file analyst confirmation.

### Warnings
- This does not enable full auto-pass. `auto_pass_eligible` remains false in all returned variant matches.
- Variants are still Excel-only in the gated reuse path. PDF/image OCR mappings remain deterministic/profile-based until an OCR-specific review design exists.
- There is still no frontend admin/review UI for listing/promoting variants; use the API endpoints for now.

### Failed attempts / Notes
- Initial focused tests exposed that `repair_suggested_mapping` could re-fill `amount` after a debit/credit variant was merged. The helper now preserves debit/credit mode.
- A targeted Vitest command initially used a repo-root path from inside `frontend/`; rerun with `src/components/steps/Step2Map.test.tsx` succeeded.
- Isolated `tests/test_bulk_processor.py` initially depended on DB tables being created by other tests; the test now patches persistence calls and runs standalone.

### Environment changes
- No new dependencies installed.
- No runtime DB migrations were applied during this session.

## Done (previous session) — Phase 2 Template Variant Persistence

### What I changed
- Implemented backend persistence for guarded bank template variants.
- Added `BankTemplateVariant` model/table with:
  - bank key, source type, sheet/header metadata
  - ordered signature + set signature
  - layout type + confirmed mapping
  - trust state: `candidate`, `verified`, `trusted`
  - usage / confirmation / correction counts
  - reviewer list and dry-run summary
- Added `services/template_variant_service.py` for:
  - upserting variants from shared mapping confirmations
  - automatic candidate -> verified/trusted promotion rules based on confirmations, reviewers, and correction rate
  - manual promotion with named reviewer requirement
  - listing variants by bank/trust state
- Changed `/api/mapping/confirm` shared-learning path:
  - `promote_shared=true` now records/updates a bank template variant
  - it no longer writes legacy `mapping_profile` or `bank_fingerprint`
  - response now includes `variant_id` and `shared_learning.trust_state`
- Added mapping variant API:
  - `GET /api/mapping/variants`
  - `POST /api/mapping/variants/{variant_id}/promote`
- Added Alembic migration `20260424_000004_add_bank_template_variants.py`
- Included variants in admin DB status counts and JSON backup/restore table specs.

### Files changed
- `persistence/models.py`
- `persistence/schemas.py`
- `services/template_variant_service.py`
- `routers/ingestion.py`
- `routers/admin.py`
- `services/admin_service.py`
- `alembic/versions/20260424_000004_add_bank_template_variants.py`
- `tests/test_template_variant_service.py`
- `tests/test_app_api.py`
- `docs/DECISIONS.md`
- `docs/HANDOFF.md`
- `docs/LOCAL_LLM_MAPPING_ROADMAP.md`

### Tests run
- Baseline before Phase 2:
  - `.venv/bin/python -m pytest tests/ -q` -> `323 passed`
  - `npm test` in `frontend/` -> `33 passed`
- Focused after Phase 2:
  - `.venv/bin/python -m pytest tests/test_template_variant_service.py tests/test_app_api.py -q` -> `46 passed`
  - `npm test -- src/components/steps/Step2Map.test.tsx src/App.workflow.test.tsx` -> `7 passed`
- Final verification:
  - `.venv/bin/python -m pytest tests/ -q` -> `327 passed`
  - `npm test` in `frontend/` -> `33 passed`
  - `npm run build` in `frontend/` -> passed, Vite large chunk warning only

### Decisions made
- Added `DEC-011`: bank template variants are persisted separately from legacy mapping profiles.
- `promote_shared=true` now means “record/update guarded variant”, not “write immediately to legacy shared memory”.
- Auto-pass is still not enabled; trusted variants exist as a lifecycle state only.

### Warnings
- Variants are not yet wired into upload/bulk suggestion selection; current upload detection still uses existing deterministic detection + legacy mapping memory.
- There is no frontend variant admin/review UI yet; variants can be listed/promoted via API.
- Manual promotion endpoint prevents demotion; demotion/revocation should be designed with audit semantics if needed later.

### Failed attempts / Notes
- Focused backend tests initially failed because older mocks still patched `save_bank_fingerprint`; tests were updated for the variant path.
- Existing uncommitted local-only cleanup/doc files from prior sessions remain part of the current worktree and were not reverted.

### Environment changes
- No new dependencies installed.
- No migrations were applied to the local runtime DB during this session; the model is available through `Base.metadata.create_all`, and the Alembic migration was added for managed upgrades.

## Done (previous session) — Phase 1 Mapping Flow Hardening

### What I changed
- เริ่ม implementation ตาม `docs/LOCAL_LLM_MAPPING_ROADMAP.md` Phase 1
- เพิ่ม backend service `services/mapping_validation_service.py` สำหรับ:
  - validate required mapping (`date`, `description`, amount path)
  - กัน duplicate column assignment
  - กัน conflict ระหว่าง signed amount กับ debit/credit
  - ตรวจ mapped column ว่ามีจริงใน uploaded sheet
  - สร้าง dry-run preview จาก sample rows โดย parse date/time/amount/direction/balance
- เพิ่ม endpoint `POST /api/mapping/preview`
- ปรับ `POST /api/mapping/confirm` ให้:
  - validate + dry-run ก่อนบันทึก
  - reject invalid mapping ก่อน learning write
  - confirm สำหรับ run ปัจจุบันเป็น default
  - ไม่ promote shared mapping/bank memory เว้นแต่ส่ง `promote_shared=true`
  - require named reviewer สำหรับ shared promotion
  - audit run-level mapping confirmation เมื่อไม่ได้ promote
- ปรับ frontend Step 2 ให้:
  - แสดง `Mapping Validation` card
  - block ปุ่ม confirm เมื่อเจอ conflict
  - แสดง conflict badge ใน mapping table
  - call preview endpoint ก่อน confirm จริง
  - ส่ง `sample_rows` และ `promote_shared:false` ใน confirm flow
- เพิ่ม/อัปเดต regression tests backend และ frontend workflow

### Files changed
- `services/mapping_validation_service.py`
- `persistence/schemas.py`
- `routers/ingestion.py`
- `frontend/src/api.ts`
- `frontend/src/components/steps/Step2Map.tsx`
- `frontend/src/components/steps/Step2Map.test.tsx`
- `frontend/src/App.workflow.test.tsx`
- `tests/test_app_api.py`
- `docs/DECISIONS.md`
- `docs/HANDOFF.md`

### Tests run
- Baseline before changes:
  - `.venv/bin/python -m pytest tests/ -q` -> `320 passed`
  - `npm test` in `frontend/` -> `33 passed`
- Focused after changes:
  - `.venv/bin/python -m pytest tests/test_app_api.py -q` -> `42 passed`
  - `npm test -- src/components/steps/Step2Map.test.tsx` -> `5 passed`
- Final verification:
  - `.venv/bin/python -m pytest tests/ -q` -> `323 passed`
  - `npm test` in `frontend/` -> `33 passed`
  - `npm run build` in `frontend/` -> passed, Vite large chunk warning only

### Decisions made
- Added `DEC-010`: `/api/mapping/confirm` no longer promotes shared memory by default
- Shared mapping/bank memory promotion is opt-in and named-reviewer gated until template variants exist
- Preview endpoint returns `status: invalid` with structured errors instead of throwing, so UI can show conflicts without treating preview as transport failure

### Warnings
- `Learn New Bank` modal still uses the older bank-template learning path; variant lifecycle is not implemented yet
- `promote_shared=true` still writes to current mapping/bank memory, not to the future variant tables
- This phase does not yet add template variant persistence, trust states, or auto-pass rollout

### Failed attempts / Notes
- Full frontend test initially failed because `App.workflow.test.tsx` did not mock the new `previewMapping` API; updated the test harness and reran successfully
- Existing uncommitted local-only cleanup/doc files from prior sessions remain in the worktree and were not reverted

### Environment changes
- No new dependencies installed
- `npm run build` regenerated build output under `static/dist`, but no tracked static build files changed

## Done (previous session) — Planning handoff for Mapping + Local LLM work

### What I changed
- สรุปแผนงานรอบใหม่และสร้าง `docs/LOCAL_LLM_MAPPING_ROADMAP.md`
- ล็อก decisions สำคัญใน `docs/DECISIONS.md` เรื่อง:
  - guarded shared template variants
  - no auto-pass for new templates
  - trusted Excel variants only for future auto-pass
  - baseline local model split for text / vision / fast fallback
- เตรียม handoff ให้ session ใหม่เริ่มงานจาก `Phase 1: Harden Current Mapping Flow`

### Files changed
- `docs/LOCAL_LLM_MAPPING_ROADMAP.md`
- `docs/DECISIONS.md`
- `docs/HANDOFF.md`

### Tests run
- ไม่มีการรัน tests รอบนี้ เพราะเป็น session วางแผน/เอกสาร

## Done (previous session) — Return BSIE to local-only development

### What I changed
- ถอด cloud-demo integration ที่ยังค้าง uncommitted ออกจาก repo
- เพิ่ม `docs/CLOUD_RESTORE.md` เป็น checklist สำหรับกลับไปใช้ Vercel/Supabase/Fly ภายหลัง
- คืน `persistence/base.py` ให้ใช้ SQLite local แบบตายตัวอีกครั้ง
- คืน `services/auth_service.py` ให้ใช้ local token path เท่านั้น
- คืน `app.py` CORS ให้เหลือ origin สำหรับ local dev/same-origin ตามเดิม
- ถอด Supabase login gate ออกจาก frontend และลบ Supabase client files
- ลบไฟล์ deploy/config ที่เพิ่มมาเพื่อ Vercel/Fly/Render:
  - `vercel.json`
  - `.vercelignore`
  - `Dockerfile`
  - `fly.toml`
  - `render.yaml`
  - `requirements-cloud.txt`
  - frontend env files สำหรับ cloud build
- ลบ dependency `@supabase/supabase-js` ออกจาก `frontend/package.json` และ lockfile
- คง `httpx` ไว้ใน `requirements.txt` เพราะ `services/llm_service.py` ยังใช้อยู่ ไม่เกี่ยวกับ Supabase อย่างเดียว
- คง `frontend/src/api.ts` ไว้เป็น fetch wrapper เล็ก ๆ สำหรับ optional `VITE_API_BASE_URL` แต่ไม่ inject auth token แล้ว

### Files changed
- Backend/runtime:
  - `app.py`
  - `persistence/base.py`
  - `services/auth_service.py`
  - `requirements.txt`
  - `.env.example`
- Frontend/runtime:
  - `frontend/src/api.ts`
  - `frontend/src/main.tsx`
  - `frontend/vite.config.ts`
  - `frontend/package.json`
  - `frontend/package-lock.json`
- Tests/docs:
  - `tests/test_persistence_base.py`
  - `docs/CLOUD_RESTORE.md`
  - `docs/DECISIONS.md`
  - `docs/HANDOFF.md`

### Files removed
- `.dockerignore`
- `.vercelignore`
- `Dockerfile`
- `fly.toml`
- `render.yaml`
- `requirements-cloud.txt`
- `vercel.json`
- `services/supabase_auth.py`
- `tests/test_supabase_auth.py`
- `frontend/.env.example`
- `frontend/.env.production`
- `frontend/src/components/Login.tsx`
- `frontend/src/components/LoginGate.tsx`
- `frontend/src/lib/supabase.ts`
- `frontend/src/lib/useAuth.ts`

### Tests run
- `.venv/bin/python -m pytest tests/ -q` -> `320 passed`
- `npm test` (in `frontend/`) -> `33 passed`

## What's Next

1. เดินหน้าพัฒนา local-first ต่อได้เลยโดยใช้ backend `127.0.0.1:8757` + frontend `127.0.0.1:6776`
2. ถ้าจะกลับไปทำ cloud deploy อีกครั้ง ให้เริ่มเป็นงานใหม่บน branch แยก ไม่ควร revive handoff/cloud config ชุดนี้ตรง ๆ
3. ถ้าจะ restore cloud ให้ใช้ `docs/CLOUD_RESTORE.md` เป็น checklist กลาง
4. งานรอบใหม่ให้เริ่มจาก `docs/LOCAL_LLM_MAPPING_ROADMAP.md`
5. เป้าหมาย implementation รอบถัดไป:
   - เชื่อม template variants เข้ากับ upload/bulk suggestion path แบบ gated
   - เพิ่ม frontend/admin review UI สำหรับ variant promotion
   - เริ่ม Phase 3: Local LLM mapping-assist เฉพาะเคส ambiguous
6. เดินงานค้างเดิมต่อได้:
   - SPNI Sprint 0-2 / Sprint 3
   - Pydantic response models สำหรับ SPNI endpoints
   - ADR-005 legacy table migration

## Decisions Made

- ย้อน runtime กลับเป็น local-only แบบชัดเจน แทนการซ่อน cloud path ไว้หลัง env flags
- ถอด auth/db/deploy integration ของ Supabase/Vercel/Fly ออกจาก working tree ไปเลย เพื่อให้ handoff และ dev flow ตรงกับการใช้งานจริง
- เก็บ `httpx` ไว้ เพราะยังเป็น dependency ของ LLM service
- ผู้ใช้ทุกคน confirm mapping สำหรับรอบงานปัจจุบันได้ แต่ shared learning ต้องผ่าน variant lifecycle
- template ใหม่ไม่ auto-pass
- auto-pass เปิดได้เฉพาะ trusted Excel variants
- `/api/mapping/confirm` เป็น run confirmation by default; shared promotion ต้อง opt-in ด้วย `promote_shared=true`
- `promote_shared=true` จะบันทึก guarded bank template variant ไม่เขียน legacy mapping profile/bank fingerprint ทันที
- local model baseline:
  - text: `qwen2.5:14b`
  - vision/doc: `qwen2.5vl:7b`
  - fast fallback: `gemma4:e4b`

## Warnings

- รอบนี้ **ไม่ได้ลบ remote resources จริง** บน Vercel/Supabase/Fly; แค่ถอดความผูกกับ repo/local runtime
- local private env files ที่ไม่ได้ track เช่น `frontend/.env.local` อาจยังมีค่า cloud เดิมอยู่ ถ้าจะ cleanup ให้ตรวจเองก่อน
- `BSIE_AUTH_REQUIRED` ยังทำงานตาม `.env`; ถ้าเปิดไว้แต่ไม่มี token valid ระบบก็ยังบังคับ auth ตาม local flow
- `docs/.handoff-snapshot.md` ยังไม่มีเหมือนเดิม
- current code ยังใช้ default model strings ฝั่ง LLM ที่เป็น `gemma4:*`; model env split ยังเป็นงานรอบถัดไป
- Phase 1 mapping hardening ถูก implement แล้ว แต่ variant lifecycle ยังไม่ถูก implement
- Variant persistence/lifecycle backend ถูก implement แล้ว แต่ยังไม่ถูกใช้ใน upload/bulk suggestion path

## Failed Attempts / Notes

- คำสั่ง `npm test -- --runInBand` ใช้ไม่ได้กับ Vitest เวอร์ชันใน repo นี้; ใช้ `npm test` ตรง ๆ แทนแล้วผ่าน
- cloud demo worktree จาก session ก่อนหน้าไม่ได้ถูก commit และถูกยกเลิกตามความต้องการ local-first รอบนี้
- การให้ผู้ใช้ทุกคนสอน shared template ตรง ๆ ถูกประเมินว่าเสี่ยงเกินไปสำหรับ evidentiary workflow; จึงเปลี่ยนทิศทางเป็น guarded variant promotion
- frontend workflow tests ต้อง mock `previewMapping` เพราะ Step 2 เรียก dry-run ก่อน confirm
- tests ที่ mock shared promotion ต้อง mock `upsert_template_variant` แทน legacy `save_profile` / `save_bank_fingerprint`

## Environment Changes

- ลบ frontend dependency `@supabase/supabase-js`
- ไม่ได้เพิ่ม dependency ใหม่
- ลบ local `.vercel/` metadata directory ออกจาก workspace
- ไม่มี environment changes รอบ planning session นี้
- ไม่มี environment changes จาก Phase 1 mapping hardening
- ไม่มี environment changes จาก Phase 2 template variant persistence

---

## Recent History

- Codex (GPT-5), 2026-04-24
  - Implement Phase 2 template variant persistence/lifecycle backend and API
  - ยืนยันผล: backend `327 passed`, frontend `33 passed`, frontend build passed
- Codex (GPT-5), 2026-04-24
  - Implement Phase 1 mapping hardening: backend validation, dry-run preview, run-only confirm default, Step2 conflict UI
  - ยืนยันผล: backend `323 passed`, frontend `33 passed`, frontend build passed
- Codex (GPT-5), 2026-04-24
  - สรุป roadmap สำหรับ Mapping + Local LLM และเตรียม handoff สำหรับ session ใหม่
  - สร้าง `docs/LOCAL_LLM_MAPPING_ROADMAP.md`
  - เพิ่ม decisions เรื่อง shared variants, auto-pass policy, และ local model baseline
- Codex (GPT-5), 2026-04-23
  - ถอด Vercel + Supabase + Fly integration ออกจาก repo เพื่อกลับไปพัฒนา local-only
  - ยืนยันผล: backend `320 passed`, frontend `33 passed`
- Claude Code (Opus 4.7), 2026-04-21
  - สร้าง cloud demo แบบ Vercel + Fly.io + Supabase ใน working tree เดิม
  - งานชุดนี้ถูก supersede แล้วโดย local-only decision วันที่ 2026-04-23
- Codex (GPT-5), 2026-04-16
  - แก้ report/export scoping regressions และเพิ่ม regression tests
- Codex (GPT-5), 2026-04-15
  - แก้ persistence/runtime isolation และ evidence storage hardening
