# Handoff Log

> อัพเดตทุกครั้งก่อนสลับ agent หรือจบ session
> Agent ตัวถัดไปจะอ่านไฟล์นี้เป็นอย่างแรก

## Current State

- **Last agent:** Codex (GPT-5)
- **Date:** 2026-04-24
- **Branch:** `Smarter-BSIE`
- **Runtime mode:** local-only อีกครั้ง
- **Baseline:** backend `372 passed`, frontend `46 passed`, frontend build passed without Vite chunk-size warning
- **Auth/DB:** local JWT auth + local SQLite WAL (`bsie.db`)
- **Cloud status:** repo ไม่ผูกกับ Vercel, Fly.io, หรือ Supabase แล้วใน working tree ปัจจุบัน

## Done (latest session) — OCR Bounding Box Overlay For Image Evidence

### What I changed
- `services/account_presence_service.py` now carries OCR token `bbox` lineage into match locations as `ocr_bbox`.
- Step 2 evidence preview drawer prefers `ocr_bbox` to draw a rectangular overlay over image evidence.
- If a valid bbox is missing, the drawer still falls back to the prior center-point marker from `x_center` / `y_center`.
- The image marker metadata now reports rectangle percentages (`x`, `y`, `w`, `h`) when a bbox is available.
- Updated backend and frontend regressions for OCR bbox preservation and image overlay placement.

### Files changed
- `services/account_presence_service.py`
- `frontend/src/components/steps/Step2Map.tsx`
- `frontend/src/components/steps/Step2Map.test.tsx`
- `tests/test_account_presence_service.py`
- `docs/DECISIONS.md`
- `docs/HANDOFF.md`

### Tests run
- Baseline before edits:
  - `.venv/bin/python -m pytest tests/ -q` -> `372 passed`
  - `npm test -- --run src/components/steps/Step2Map.test.tsx` in `frontend/` -> `13 passed`
- Focused:
  - `.venv/bin/python -m py_compile services/account_presence_service.py` -> passed
  - `.venv/bin/python -m pytest tests/test_account_presence_service.py::test_verify_account_presence_scans_image_raw_ocr_tokens_when_table_is_empty -q` -> `1 passed`
  - `npm test -- --run src/components/steps/Step2Map.test.tsx` in `frontend/` -> `13 passed`
  - `npm run build` in `frontend/` -> passed without Vite chunk-size warning
- Full verification:
  - `.venv/bin/python -m pytest tests/ -q` -> `372 passed`
  - `npm test -- --run` in `frontend/` -> `46 passed`

### Decisions made
- Added DEC-034: OCR account presence locations preserve bounding boxes for evidence overlays.

### Warnings / Next
- OCR bbox overlays are available only for OCR token matches that include bbox lineage. OCR table/page-text/PDF table matches still use row/column/page metadata.
- The next useful slice is Phase 4 investigation copilot scope locking, or carrying PDF text coordinates if we want PDF-region overlays later.

### Environment changes
- No dependencies installed.

## Done (previous session) — OCR Marker Overlay For Image Evidence

### What I changed
- Step 2 evidence preview drawer now renders image evidence as an `<img>` instead of an iframe.
- When an account-presence location includes OCR `x_center` / `y_center`, the drawer draws a visible marker over the source image after the image dimensions load.
- The metadata panel now shows the marker position as percentages of the image dimensions.
- PDF evidence still uses the existing iframe preview and keeps the `#page=N` fragment.
- Updated the OCR lineage frontend regression to verify the image preview URL, marker placement, and `Open in new tab` URL.

### Files changed
- `frontend/src/components/steps/Step2Map.tsx`
- `frontend/src/components/steps/Step2Map.test.tsx`
- `docs/HANDOFF.md`

### Tests run
- Baseline before edits:
  - `.venv/bin/python -m pytest tests/ -q` -> `372 passed`
  - `npm test -- --run src/components/steps/Step2Map.test.tsx` in `frontend/` -> `13 passed`
- Focused:
  - `npm test -- --run src/components/steps/Step2Map.test.tsx` in `frontend/` -> `13 passed`
  - `npm run build` in `frontend/` -> passed without Vite chunk-size warning
- Full verification:
  - `npm test -- --run` in `frontend/` -> `46 passed`

### Decisions made
- No new architecture decision. This is a UI overlay improvement inside the DEC-033 evidence preview boundary.

### Warnings / Next
- The overlay marks OCR center coordinates only. It does not yet draw full OCR bounding boxes because account-presence locations currently expose `x_center`/`y_center` but not the full bbox.
- The next useful slice is to carry OCR bbox coordinates through account-presence locations, or move into Phase 4 investigation copilot scope locking.

### Environment changes
- No dependencies installed.

## Done (previous session) — Inline Evidence Preview Drawer

### What I changed
- Step 2 account-presence location cards now open an inline evidence preview drawer instead of only linking to a new tab.
- The drawer embeds the existing `/api/files/{file_id}/evidence-preview` URL and keeps the PDF `#page=N` fragment when page lineage is present.
- The drawer shows the selected match metadata next to the evidence: source region, match type, OCR confidence, page/token/row/column label, OCR x/y position, and raw preview.
- The drawer still includes an `Open in new tab` link for analysts who need a larger browser view.
- Updated the OCR lineage frontend regression to assert the drawer URL and metadata.

### Files changed
- `frontend/src/components/steps/Step2Map.tsx`
- `frontend/src/components/steps/Step2Map.test.tsx`
- `docs/HANDOFF.md`

### Tests run
- Baseline before edits:
  - `.venv/bin/python -m pytest tests/ -q` -> `372 passed`
  - `npm test -- --run src/components/steps/Step2Map.test.tsx` in `frontend/` -> `13 passed`
- Focused:
  - `npm test -- --run src/components/steps/Step2Map.test.tsx` in `frontend/` -> `13 passed`
  - `npm run build` in `frontend/` -> passed without Vite chunk-size warning
- Full verification:
  - `npm test -- --run` in `frontend/` -> `46 passed`

### Decisions made
- No new architecture decision. This is the UI drawer implementation of the preview policy recorded in DEC-033.

### Warnings / Next
- The drawer embeds the source PDF/image but does not yet draw OCR bounding-box overlays on top of the document.
- The next useful slice is either OCR box highlight overlay for image previews or Phase 4 investigation copilot scope locking.

### Environment changes
- No dependencies installed.

## Done (previous session) — Evidence Preview Links From Account Presence

### What I changed
- Added `/api/files/{file_id}/evidence-preview` in `routers/results.py`.
- The endpoint validates UUID-style `file_id`, resolves the DB `FileRecord`, confines the resolved path to `EVIDENCE_DIR`, and serves only PDF/image evidence inline.
- Step 2 account-presence location cards now show an `Open evidence` link for previewable PDF/image evidence.
- PDF links include `#page=N` when account-presence lineage reports a page number.
- Added backend regressions for inline preview serving and path-confinement rejection.

### Files changed
- `routers/results.py`
- `frontend/src/api.ts`
- `frontend/src/components/steps/Step2Map.tsx`
- `frontend/src/components/steps/Step2Map.test.tsx`
- `tests/test_app_api.py`
- `docs/DECISIONS.md`
- `docs/HANDOFF.md`

### Tests run
- Baseline before edits:
  - `.venv/bin/python -m pytest tests/ -q` -> `370 passed`
  - `npm test -- --run src/components/steps/Step2Map.test.tsx` in `frontend/` -> `13 passed`
- Focused:
  - `.venv/bin/python -m py_compile routers/results.py` -> passed
  - `.venv/bin/python -m pytest tests/test_app_api.py::test_file_evidence_preview_serves_pdf_inline_from_evidence_storage tests/test_app_api.py::test_file_evidence_preview_rejects_paths_outside_evidence_storage -q` -> `2 passed`
  - `npm test -- --run src/components/steps/Step2Map.test.tsx` in `frontend/` -> `13 passed`
  - `npm run build` in `frontend/` -> passed without Vite chunk-size warning
- Full verification:
  - `.venv/bin/python -m pytest tests/ -q` -> `372 passed`
  - `npm test -- --run` in `frontend/` -> `46 passed`

### Decisions made
- Added DEC-033: evidence preview opens only stored PDF/image evidence by `file_id`.

### Warnings / Next
- The preview endpoint intentionally does not serve Excel evidence. Excel account-presence locations remain row/column references for now.
- The browser can open the PDF/image and PDF page fragment, but BSIE does not yet draw a highlighted OCR bounding box overlay on the document itself.
- Next useful slice: build a small evidence preview drawer with OCR/page highlight metadata, or move into Phase 4 investigation copilot scope locking.

### Environment changes
- No dependencies installed.

## Done (previous session) — OCR Account Presence Review UI

### What I changed
- Step 2 now surfaces richer account-presence lineage after `Verify Evidence`.
- Exact and possible leading-zero matches are displayed separately.
- Each returned location now shows source region (`page_text`, `pdf_table`, `ocr_table`, `ocr_token`, etc.), page/line/row/column or OCR token position, match type, OCR confidence when available, OCR x/y center when available, and raw value preview.
- Account-presence summary chips now show source file type plus scan counts such as pages, tables, cells, OCR tokens, and returned locations.
- Added a frontend regression for OCR-token account-presence lineage display.

### Files changed
- `frontend/src/components/steps/Step2Map.tsx`
- `frontend/src/components/steps/Step2Map.test.tsx`
- `docs/HANDOFF.md`

### Tests run
- Baseline before edits:
  - `.venv/bin/python -m pytest tests/ -q` -> `370 passed`
  - `npm test -- --run src/components/steps/Step2Map.test.tsx` in `frontend/` -> `12 passed`
- Focused:
  - `npm test -- --run src/components/steps/Step2Map.test.tsx` in `frontend/` -> `13 passed`
  - `npm run build` in `frontend/` -> passed without Vite chunk-size warning
- Full verification:
  - `.venv/bin/python -m pytest tests/ -q` -> `370 passed`
  - `npm test -- --run` in `frontend/` -> `46 passed`

### Decisions made
- No new architecture decision. This is a frontend evidence-review presentation improvement on top of DEC-030/DEC-031.

### Warnings / Next
- The UI now displays available OCR/page lineage, but it still depends on the deterministic account-presence service returning those fields.
- The next useful slice is to let investigators jump from a match row/token to a document preview region, or continue toward Phase 4 investigation copilot scope locking.

### Environment changes
- No dependencies installed.

## Done (previous session) — Frontend Workflow Code-Splitting

### What I changed
- `frontend/src/App.tsx` now lazy-loads the five workflow step components (`Step1Upload` through `Step5Results`) instead of importing them into the initial app chunk.
- The existing page-level lazy boundaries for Dashboard, Bank Manager, Bulk Intake, and Investigation Desk remain in place.
- `frontend/vite.config.ts` now sets `chunkSizeWarningLimit: 900` because the remaining large chunk is the deliberately isolated Cytoscape graph runtime.
- `frontend/src/App.workflow.test.tsx` now waits for lazy-rendered workflow elements before querying them.

### Files changed
- `frontend/src/App.tsx`
- `frontend/src/App.workflow.test.tsx`
- `frontend/vite.config.ts`
- `docs/DECISIONS.md`
- `docs/HANDOFF.md`

### Tests run
- Baseline before edits:
  - `.venv/bin/python -m pytest tests/ -q` -> `370 passed`
  - `npm test -- --run` in `frontend/` -> `45 passed`
- Full verification:
  - `.venv/bin/python -m pytest tests/ -q` -> `370 passed`
  - `npm test -- --run` in `frontend/` -> `45 passed`
  - `npm run build` in `frontend/` -> passed without Vite chunk-size warning

### Decisions made
- Added DEC-032: frontend workflow steps are lazy-loaded to keep the main bundle small.

### Warnings / Next
- The initial app chunk is now about `360 kB`, down from about `1,209 kB` before this split.
- Cytoscape remains about `803 kB` as a lazy graph-runtime chunk. If future graph work pushes that above the `900 kB` threshold, revisit deeper graph-specific splitting instead of raising the limit again.
- Next useful slice: richer OCR review UI that displays token/page locations, or continue hardening unknown-bank/account conflict review screens.

### Environment changes
- No dependencies installed.

## Done (previous session) — Raw OCR Token Account Presence Verification

### What I changed
- `core.image_loader.parse_image_file` now preserves accepted OCR text boxes as `ocr_tokens` alongside the reconstructed table DataFrame.
- OCR tokens include text, confidence, page number, bbox, and x/y centers so downstream checks can retain lineage.
- `services/account_presence_service.py` now scans OCR table cells and raw OCR tokens for image/scanned-PDF evidence.
- OCR token matches report `source_region=ocr_token`, `column_label=ocr_token`, OCR confidence, page number, and position metadata.
- Account-presence summaries now include `ocr_tokens_scanned`.
- Added regressions for OCR token lineage extraction and account verification when OCR tokens contain the account but table reconstruction is empty.

### Files changed
- `core/image_loader.py`
- `services/account_presence_service.py`
- `tests/test_image_loader.py`
- `tests/test_account_presence_service.py`
- `docs/DECISIONS.md`
- `docs/HANDOFF.md`
- `docs/LOCAL_LLM_MAPPING_ROADMAP.md`

### Tests run
- Baseline before edits:
  - `.venv/bin/python -m pytest tests/ -q` -> `368 passed`
  - `npm test -- --run` in `frontend/` -> `45 passed`
- Focused:
  - `.venv/bin/python -m py_compile core/image_loader.py services/account_presence_service.py` -> passed
  - `.venv/bin/python -m pytest tests/test_image_loader.py tests/test_account_presence_service.py -q` -> `14 passed`
- Full verification:
  - `.venv/bin/python -m pytest tests/ -q` -> `370 passed`
  - `npm test -- --run` in `frontend/` -> `45 passed`
  - `npm run build` in `frontend/` -> passed; Vite chunk-size warning only
  - `.venv/bin/python -m py_compile core/image_loader.py services/account_presence_service.py` -> passed
  - `git diff --check` -> passed

### Decisions made
- Added DEC-031: OCR account presence scans raw accepted text tokens.

### Warnings / Next
- Raw OCR token scanning still depends on EasyOCR availability and the existing confidence threshold.
- Token matches may duplicate table-cell matches because both are valid deterministic search units; use `source_region` and location metadata to distinguish them.
- Vite still reports the existing large main chunk warning; correctness tests/build pass.
- Next useful slice: frontend code-splitting for the Vite chunk warning, or richer OCR review UI that displays token/page locations.

### Environment changes
- No dependencies installed.

## Done (previous session) — PDF/Image Account Presence Verification

### What I changed
- Extended `services/account_presence_service.py` beyond Excel workbook scanning.
- Text PDFs now scan page text lines and extracted PDF table cells deterministically.
- Image files and scanned PDFs now scan OCR table cells via the existing `core.image_loader.parse_image_file` path.
- Results now report source regions such as `page_text`, `pdf_table`, and `ocr_table`, plus page count, OCR usage, and search-unit counts.
- OCR unavailable/no searchable OCR table cells return structured warning statuses (`read_error` / `no_searchable_text`) rather than claiming an account is absent.
- Step 2 label changed from `Verify in Workbook` to `Verify Evidence` because the action now covers Excel, PDF, and image evidence.
- Added service and API regressions for PDF text scanning and image OCR table scanning/failure behavior.

### Files changed
- `services/account_presence_service.py`
- `tests/test_account_presence_service.py`
- `tests/test_app_api.py`
- `frontend/src/components/steps/Step2Map.tsx`
- `frontend/src/components/steps/Step2Map.test.tsx`
- `docs/DECISIONS.md`
- `docs/HANDOFF.md`
- `docs/LOCAL_LLM_MAPPING_ROADMAP.md`

### Tests run
- Baseline before edits:
  - `.venv/bin/python -m pytest tests/ -q` -> `364 passed`
  - `npm test -- --run` in `frontend/` -> `45 passed`
- Focused:
  - `.venv/bin/python -m py_compile services/account_presence_service.py` -> passed
  - `.venv/bin/python -m pytest tests/test_account_presence_service.py tests/test_app_api.py::test_account_presence_endpoint_scans_stored_excel_file tests/test_app_api.py::test_account_presence_endpoint_scans_stored_text_pdf_file -q` -> `7 passed`
  - `npm test -- --run src/components/steps/Step2Map.test.tsx` in `frontend/` -> `12 passed`
- Full verification:
  - `.venv/bin/python -m pytest tests/ -q` -> `368 passed`
  - `npm test -- --run` in `frontend/` -> `45 passed`
  - `npm run build` in `frontend/` -> passed; Vite chunk-size warning only
  - `git diff --check` -> passed

### Decisions made
- Added DEC-030: account presence verification extends to text PDF and OCR tables fail-closed.

### Warnings / Next
- Image/scanned-PDF account presence depends on the existing OCR table reconstruction. If OCR is unavailable or produces no searchable cells, BSIE returns warning-only status rather than `not_found`.
- Raw OCR token scanning was added in the next session; see latest section.
- Vite still reports the existing large main chunk warning; correctness tests/build pass.
- Next useful slice: add raw OCR token scanning for account presence, or tackle frontend code-splitting to reduce the Vite chunk warning.

### Environment changes
- No dependencies installed.

## Done (previous session) — Account Presence Review Gate Policy

### What I changed
- Extended the Step 2 review gate so account-presence verification results can block progression.
- `not_found` and `possible_leading_zero_loss` now require the analyst to click `Confirm Known Account` before Step 3.
- `exact_found` remains auto-cleared; unsupported/read-error style statuses remain visible warnings until deterministic PDF/image/OCR verification has an equivalent policy.
- Moved `accountPresence` from local `Step2Map` state into Zustand so `canProceedToConfig` and the final confirm button use the same centralized gate state.
- Clearing/changing the known account clears stale workbook verification and resets account review.
- Added frontend regression tests for review-gate logic and the real Step 2 verify/confirm workflow.

### Files changed
- `frontend/src/lib/reviewGate.ts`
- `frontend/src/store.ts`
- `frontend/src/components/steps/Step2Map.tsx`
- `frontend/src/lib/reviewGate.test.ts`
- `frontend/src/components/steps/Step2Map.test.tsx`
- `docs/DECISIONS.md`
- `docs/HANDOFF.md`
- `docs/LOCAL_LLM_MAPPING_ROADMAP.md`

### Tests run
- Baseline before edits:
  - `.venv/bin/python -m pytest tests/ -q` -> `364 passed`
  - `npm test -- --run` in `frontend/` -> `42 passed`
- Focused:
  - `npm test -- --run src/lib/reviewGate.test.ts src/components/steps/Step2Map.test.tsx` in `frontend/` -> `21 passed`
- Full verification:
  - `.venv/bin/python -m pytest tests/ -q` -> `364 passed`
  - `npm test -- --run` in `frontend/` -> `45 passed`
  - `npm run build` in `frontend/` -> passed; Vite chunk-size warning only

### Decisions made
- Added DEC-029: negative account-presence verification requires analyst confirmation.

### Warnings / Next
- Account-presence blocking is currently deterministic for Excel verification results only.
- PDF/image/OCR sources still need a deterministic equivalent before their verification status should become a hard block.
- Next useful slice: design OCR/PDF account-presence verification or start splitting the large Vite main chunk with lazy-loaded investigation/workflow surfaces.

### Environment changes
- No dependencies installed.

## Done (previous session) — Deterministic Account Presence Verification

### What I changed
- Added `services/account_presence_service.py` to scan Excel workbook cells deterministically for a selected subject account.
- Added `/api/mapping/account-presence`, resolving evidence by `file_id` and confining reads to `EVIDENCE_DIR`.
- The verifier scans raw worksheet cells with `header=None`, reports sheet/row/column locations, row zone (`pre_header`, `header`, `body`), exact matches, and possible leading-zero-loss candidates.
- Step 2 now has a `Verify in Workbook` action in Known Account Context and displays verification status plus first match locations.
- Mapping assist, vision assist, and mapping confirmation can now receive `account_presence`; `subject_context` includes workbook presence status/summary.
- Added backend/frontend regression tests for service behavior, API path confinement/use, and Step 2 verification handoff into confirm audit context.

### Files changed
- `services/account_presence_service.py`
- `services/subject_context_service.py`
- `services/mapping_assist_service.py`
- `routers/ingestion.py`
- `persistence/schemas.py`
- `frontend/src/api.ts`
- `frontend/src/components/steps/Step2Map.tsx`
- `frontend/src/components/steps/Step2Map.test.tsx`
- `frontend/src/App.workflow.test.tsx`
- `tests/test_account_presence_service.py`
- `tests/test_app_api.py`
- `docs/DECISIONS.md`
- `docs/HANDOFF.md`
- `docs/LOCAL_LLM_MAPPING_ROADMAP.md`

### Tests run
- `.venv/bin/python -m pytest tests/test_account_presence_service.py tests/test_subject_context_service.py tests/test_mapping_assist_service.py tests/test_app_api.py::test_account_presence_endpoint_scans_stored_excel_file tests/test_app_api.py::test_mapping_confirm_endpoint_weights_corrected_feedback_from_override_context tests/test_app_api.py::test_mapping_assist_endpoint_uses_selected_bank_as_authority -q` -> `14 passed`
- `npm test -- --run src/components/steps/Step2Map.test.tsx src/App.workflow.test.tsx` in `frontend/` -> `13 passed`
- `.venv/bin/python -m py_compile services/account_presence_service.py services/subject_context_service.py services/mapping_assist_service.py routers/ingestion.py persistence/schemas.py` -> passed
- `.venv/bin/python -m pytest tests/ -q` -> `364 passed`
- `npm test -- --run` in `frontend/` -> `42 passed`
- `npm run build` in `frontend/` -> passed; Vite chunk-size warning only

### Decisions made
- Added DEC-028: account presence verification scans stored workbook evidence deterministically.

### Warnings / Next
- Account presence verification is deterministic for Excel only. PDF/image/OCR sources currently return structured unsupported/not-found style feedback rather than claiming full scan coverage.
- The verification result is visible and audited, but it does not yet add a separate mandatory block when an otherwise valid account is not found.
- Next useful slice: decide policy for whether `not_found` or `possible_leading_zero_loss` should require explicit analyst confirmation, and design an OCR/PDF equivalent if needed.

### Environment changes
- No dependencies installed.

## Done (previous session) — Known Account Context in Mapping Review

### What I changed
- Added Step 2 known-account context controls for subject account and holder name, reusing upload identity guesses as initial values.
- Added a review gate for account conflicts: if the analyst-selected account differs from the statement-inferred account, Step 2 blocks until the analyst explicitly confirms the known account.
- Added `subject_context` construction with account normalization, inferred account/name, match status, and sample-row observation.
- Threaded `subject_context` through text mapping assist, vision mapping assist, and `/api/mapping/confirm` audit context.
- Updated mapping assist prompts so local LLMs may use the subject account for statement perspective but must not change or invent account values.
- Added regression tests for review gate behavior, Step 2 blocking, mapping assist prompt/response context, API context forwarding, and account normalization.

### Files changed
- `frontend/src/lib/reviewGate.ts`
- `frontend/src/store.ts`
- `frontend/src/api.ts`
- `frontend/src/components/steps/Step2Map.tsx`
- `persistence/schemas.py`
- `routers/ingestion.py`
- `services/subject_context_service.py`
- `services/mapping_assist_service.py`
- `frontend/src/lib/reviewGate.test.ts`
- `frontend/src/components/steps/Step2Map.test.tsx`
- `tests/test_subject_context_service.py`
- `tests/test_mapping_assist_service.py`
- `tests/test_app_api.py`
- `docs/DECISIONS.md`
- `docs/HANDOFF.md`
- `docs/LOCAL_LLM_MAPPING_ROADMAP.md`

### Tests run
- `.venv/bin/python -m pytest tests/test_subject_context_service.py tests/test_mapping_assist_service.py tests/test_app_api.py::test_mapping_confirm_endpoint_weights_corrected_feedback_from_override_context tests/test_app_api.py::test_mapping_assist_endpoint_uses_selected_bank_as_authority -q` -> `11 passed`
- `npm test -- --run src/lib/reviewGate.test.ts src/components/steps/Step2Map.test.tsx` in `frontend/` -> `17 passed`
- `.venv/bin/python -m py_compile services/subject_context_service.py services/mapping_assist_service.py routers/ingestion.py persistence/schemas.py` -> passed
- `.venv/bin/python -m pytest tests/ -q` -> `361 passed`
- `npm test -- --run` in `frontend/` -> `41 passed`
- `npm run build` in `frontend/` -> passed; Vite chunk-size warning only

### Decisions made
- Added DEC-027: analyst-selected subject account is review-gated mapping context.

### Warnings / Next
- Account conflict detection currently uses upload identity inference plus sampled rows. It does not yet scan the full workbook body/header on demand for a selected account.
- Next useful slice: add a deterministic account-presence verification service/endpoint that checks the selected sheet/header and reports where the known account appears before pipeline processing.

### Environment changes
- No dependencies installed.

## Done (previous session) — Known Bank Override Authority

### What I changed
- Made Step 2 treat selected-bank mismatch as an explicit review blocker even when auto-detection confidence is high.
- Added a visible warning when the selected bank overrides auto-detection.
- Updated review gate state so `bankOverrideDetected` participates in `bankNeedsReview` and `canProceedToConfig`.
- Updated mapping assist prompt/context so the selected bank is the analyst-selected authority for the run; conflicts are warning-only and mapping still happens under the selected bank.
- Updated `/api/mapping/confirm` to return and audit `bank_authority`, including selected bank, detected bank, override flag, and feedback status.
- Added regression tests for frontend bank override blocking, LLM authority prompt/response metadata, and backend audit context.

### Files changed
- `frontend/src/lib/reviewGate.ts`
- `frontend/src/store.ts`
- `frontend/src/components/steps/Step2Map.tsx`
- `services/mapping_assist_service.py`
- `routers/ingestion.py`
- `frontend/src/lib/reviewGate.test.ts`
- `frontend/src/components/steps/Step2Map.test.tsx`
- `tests/test_mapping_assist_service.py`
- `tests/test_app_api.py`
- `docs/DECISIONS.md`
- `docs/HANDOFF.md`
- `docs/LOCAL_LLM_MAPPING_ROADMAP.md`

### Tests run
- `.venv/bin/python -m pytest tests/test_mapping_assist_service.py tests/test_app_api.py::test_mapping_confirm_endpoint_weights_corrected_feedback_from_override_context tests/test_app_api.py::test_mapping_assist_endpoint_uses_selected_bank_as_authority -q` -> `8 passed`
- `npm test -- --run src/lib/reviewGate.test.ts src/components/steps/Step2Map.test.tsx` in `frontend/` -> `15 passed`
- `.venv/bin/python -m py_compile services/mapping_assist_service.py routers/ingestion.py persistence/schemas.py` -> passed
- `.venv/bin/python -m pytest tests/ -q` -> `358 passed`
- `npm test -- --run` in `frontend/` -> `39 passed`
- `npm run build` in `frontend/` -> passed

### Decisions made
- Added DEC-026: analyst-selected bank is authoritative after explicit review.

### Warnings / Next
- Known account is still mostly collected in Step 3. Next slice should move/duplicate known account context earlier so it can help bank/layout review and LLM mapping assist.
- The override flow is now explicit for bank selection, but it does not yet verify whether the selected account appears in workbook body/header.

### Environment changes
- No dependencies installed.

## Done (previous session) — Balance Alias Disambiguation

### What I changed
- Added deterministic repair for ambiguous balance-like suggestions in `utils/app_helpers.py`.
- Suggestions now prefer curated statement-balance aliases such as `ยอดคงเหลือ`, `Outstanding Balance`, and `Ledger Balance` over lower-priority after-transaction aliases such as `ยอดหลังรายการ` when both are available.
- Kept `ยอดหลังรายการ` usable when no better balance alias exists.
- Added `ยอดหลังรายการ` to deterministic balance aliases so statements that only expose that header can still be mapped.
- Updated TTB config aliases and benchmark docs/decision roadmap.

### Files changed
- `utils/app_helpers.py`
- `core/column_detector.py`
- `config/ttb.json`
- `tests/test_app_helpers.py`
- `tests/test_mapping_assist_service.py`
- `docs/LOCAL_LLM_BENCHMARKS.md`
- `docs/LOCAL_LLM_MAPPING_ROADMAP.md`
- `docs/DECISIONS.md`
- `docs/HANDOFF.md`

### Benchmark results
- Targeted TTB fixture:
  - command: `.venv/bin/python scripts/benchmark_mapping_models.py --models gemma4:26b --fixture ttb_ambiguous_amount_balance --mode both --run-id balance-ttb-gemma26b-20260424120508`
  - result: `gemma4:26b` text `6/6`, vision `6/6`, validation `True` for both.
- 8-bank rerun for `gemma4:26b`:
  - command: `.venv/bin/python scripts/benchmark_mapping_models.py --models gemma4:26b --mode both --run-id balance-8bank-gemma26b-20260424120540`
  - result: text `55/55` = `100.00%`, vision `55/55` = `100.00%`, validation `True` for every fixture.

### Tests run
- `.venv/bin/python -m pytest tests/test_app_helpers.py tests/test_mapping_assist_service.py tests/test_benchmark_mapping_models.py -q` -> `11 passed`
- `.venv/bin/python -m py_compile utils/app_helpers.py core/column_detector.py services/mapping_assist_service.py scripts/benchmark_mapping_models.py` -> passed
- `.venv/bin/python -m json.tool config/ttb.json` -> passed
- `.venv/bin/python -m pytest tests/ -q` -> `356 passed`
- `git diff --check` -> passed
- Frontend was not rerun in this slice because no frontend files changed.

### Decisions made
- Added DEC-025: balance-like mapping suggestions prefer curated statement-balance aliases.

### Warnings / Next
- The current synthetic 8-bank benchmark has no `gemma4:26b` misses, but it is still synthetic. Do not use this as justification for auto-apply.
- Next useful benchmark work: add multiple variants per bank, especially real-world-looking but synthetic layouts with merged headers, missing balances, and OCR noise.

### Environment changes
- No dependencies installed.
- Generated ignored benchmark artifacts under `artifacts/llm_mapping_benchmarks/`.

## Done (previous session) — Direction-Marker Amount Path

### What I changed
- Made `amount + direction_marker` a first-class mapping path for unsigned amount layouts with `DR`/`CR`, `IN`/`OUT`, or Thai deposit/withdraw markers.
- Updated mapping validation and dry-run preview so direction-marker mappings validate cleanly and preview signed amounts/directions deterministically.
- Exposed `direction_marker` to local LLM mapping assist prompts and frontend mapping UI.
- Hardened profile/LLM mapping repair so direction-marker amount paths do not get mixed with debit/credit mappings.
- Updated `core/normalizer.py` and `config/bay.json` so runtime normalization uses the same direction-marker semantics as preview.
- Updated the synthetic BAY benchmark fixture to score `direction_marker` explicitly.

### Files changed
- `services/mapping_validation_service.py`
- `services/mapping_assist_service.py`
- `utils/app_helpers.py`
- `core/normalizer.py`
- `config/bay.json`
- `frontend/src/components/steps/Step2Map.tsx`
- `frontend/src/components/BankManager.tsx`
- `frontend/src/locales/en.json`
- `frontend/src/locales/th.json`
- `scripts/benchmark_mapping_models.py`
- `tests/test_mapping_validation_service.py`
- `tests/test_mapping_assist_service.py`
- `tests/test_normalizer_direction_marker.py`
- `frontend/src/components/steps/Step2Map.test.tsx`
- `docs/LOCAL_LLM_BENCHMARKS.md`
- `docs/LOCAL_LLM_MAPPING_ROADMAP.md`
- `docs/DECISIONS.md`
- `docs/HANDOFF.md`

### Benchmark results
- Targeted BAY fixture:
  - command: `.venv/bin/python scripts/benchmark_mapping_models.py --models gemma4:26b --fixture bay_direction_marker_amount --mode both --run-id direction-marker-bay-20260424115658`
  - result: `gemma4:26b` text `8/8`, vision `8/8`, validation `True` for both.
- 8-bank rerun for `gemma4:26b`:
  - command: `.venv/bin/python scripts/benchmark_mapping_models.py --models gemma4:26b --mode both --run-id direction-marker-8bank-gemma26b-20260424115736`
  - result: text `54/55` = `98.18%`, vision `54/55` = `98.18%`, validation `True` for every fixture.
  - remaining miss: intentional TTB balance ambiguity (`ยอดหลังรายการ` vs expected `ยอดคงเหลือ`).

### Tests run
- `.venv/bin/python -m pytest tests/test_mapping_validation_service.py tests/test_mapping_assist_service.py tests/test_normalizer_direction_marker.py tests/test_benchmark_mapping_models.py -q` -> `12 passed`
- `.venv/bin/python -m pytest tests/ -q` -> `353 passed`
- `npm test -- --run` in `frontend/` -> `37 passed`
- `npm run build` in `frontend/` -> passed
- JSON validation for `config/bay.json`, `frontend/src/locales/en.json`, and `frontend/src/locales/th.json` -> passed

### Decisions made
- Added DEC-024: direction-marker amount layouts are first-class mapping paths.
- Keep `gemma4:26b` as mapping-assist default; the BAY validation blocker is now deterministic code, not a model-quality issue.

### Warnings / Next
- The only benchmark miss left for `gemma4:26b` is the intentionally ambiguous TTB balance choice; next useful deterministic improvement is balance-column disambiguation.
- If more Thai marker words appear in real statements, add them to the marker sets in both validator and normalizer before trusting them.

### Environment changes
- No dependencies installed.
- Generated ignored benchmark artifacts under `artifacts/llm_mapping_benchmarks/`.

## Done (previous session) — Expanded 8-Bank Mapping Benchmark Fixtures

### What I changed
- Expanded `scripts/benchmark_mapping_models.py` fixtures from 3 layouts to 8 bank-covering fixtures:
  - `scb`: `thai_debit_credit`
  - `kbank`: `english_signed_amount`
  - `ktb`: `ocr_noisy_signed_amount`
  - `bbl`: `bbl_leading_zero_counterparty`
  - `bay`: `bay_direction_marker_amount`
  - `ttb`: `ttb_ambiguous_amount_balance`
  - `gsb`: `gsb_mymo_mixed_headers`
  - `baac`: `baac_scientific_counterparty`
- Added unit coverage that fixture IDs are unique and all 8 supported bank keys are represented.
- Ran expanded harness against `gemma4:26b` alone and then all default Gemma models.
- Updated benchmark docs, decision log, roadmap, and this handoff.

### Benchmark command

```bash
.venv/bin/python scripts/benchmark_mapping_models.py --run-id 20260424-expanded-8bank-gemma-comparison
```

### Benchmark results
- `gemma4:26b`:
  - text `53/54` = `98.15%`, avg `5,749.02 ms`
  - vision `53/54` = `98.15%`, avg `6,790.99 ms`
- `gemma4:e4b`:
  - text `18/54` = `33.33%`, avg `7,658.07 ms`
  - vision `21/54` = `38.89%`, avg `7,181.56 ms`
- `gemma4:e2b`:
  - text `20/54` = `37.04%`, avg `3,553.45 ms`
  - vision `4/54` = `7.41%`, avg `4,573.94 ms`

### Notes
- `gemma4:26b` missed only the intentionally ambiguous TTB balance choice (`ยอดหลังรายการ` vs expected `ยอดคงเหลือ`).
- BAY direction-marker fixture scored correct on expected fields for `gemma4:26b`, but validation returned `false` because current mapping validation has no explicit direction-marker field for unsigned amount + `DR`/`CR`.

### Files changed
- `scripts/benchmark_mapping_models.py`
- `tests/test_benchmark_mapping_models.py`
- `docs/LOCAL_LLM_BENCHMARKS.md`
- `docs/DECISIONS.md`
- `docs/HANDOFF.md`
- `docs/LOCAL_LLM_MAPPING_ROADMAP.md`

### Tests run
- `.venv/bin/python -m py_compile scripts/benchmark_mapping_models.py tests/test_benchmark_mapping_models.py` -> passed
- `.venv/bin/python -m pytest tests/test_benchmark_mapping_models.py -q` -> `4 passed`
- `.venv/bin/python -m pytest tests/ -q` -> `348 passed`
- Expanded live harness:
  - `.venv/bin/python scripts/benchmark_mapping_models.py --models gemma4:26b --run-id 20260424-expanded-8bank-gemma26b` -> passed
  - `.venv/bin/python scripts/benchmark_mapping_models.py --run-id 20260424-expanded-8bank-gemma-comparison` -> passed

### Decisions made
- Keep `gemma4:26b` as mapping-assist default; expanded fixtures make this much more convincing.
- All future mapping model comparisons should include every supported bank key.

### Warnings / Next
- Add deterministic support for direction-marker amount layouts (`DR`/`CR`, `IN`/`OUT`) so BAY-like fixtures can validate cleanly without pretending they are signed amount or debit/credit columns.
- Add more than one fixture per bank before considering any stronger automation policy.

### Environment changes
- No dependencies installed by Codex.
- Generated ignored benchmark artifacts under `artifacts/llm_mapping_benchmarks/`.

## Done (previous session) — Reproducible Mapping Model Benchmark Harness

### What I changed
- Added `scripts/benchmark_mapping_models.py`.
  - Uses only synthetic fixtures; does not read evidence, parser runs, or the DB.
  - Runs text and/or vision mapping assist against fixed mapping fixtures.
  - Scores expected logical fields against actual suggested columns.
  - Writes JSON and Markdown reports under ignored `artifacts/llm_mapping_benchmarks/`.
  - Supports `--models`, `--mode`, repeated `--fixture`, `--run-id`, `--keep-fixtures`, and `--print-json`.
- Added `tests/test_benchmark_mapping_models.py` for model parsing, scoring, summary, and Markdown output.
- Updated docs:
  - `docs/LOCAL_LLM_BENCHMARKS.md`
  - `docs/DECISIONS.md` (`DEC-022`)
  - `docs/HANDOFF.md`
  - `docs/LOCAL_LLM_MAPPING_ROADMAP.md`

### Harness command

```bash
.venv/bin/python scripts/benchmark_mapping_models.py --run-id 20260424-gemma-mapping-fixtures
```

The first committed-harness run wrote:

- `artifacts/llm_mapping_benchmarks/mapping_model_benchmark_20260424-gemma-mapping-fixtures.json`
- `artifacts/llm_mapping_benchmarks/mapping_model_benchmark_20260424-gemma-mapping-fixtures.md`

### Benchmark results from harness run
- `gemma4:26b`:
  - text `21/21` = `100%`, avg `5,759.21 ms`
  - vision `21/21` = `100%`, avg `6,204.92 ms`
- `gemma4:e4b`:
  - text `15/21` = `71.43%`, avg `7,310.27 ms`
  - vision `15/21` = `71.43%`, avg `6,454.89 ms`
- `gemma4:e2b`:
  - text `13/21` = `61.90%`, avg `4,967.51 ms`
  - vision `3/21` = `14.29%`, avg `4,664.24 ms`

### Files changed
- `scripts/benchmark_mapping_models.py`
- `tests/test_benchmark_mapping_models.py`
- `docs/LOCAL_LLM_BENCHMARKS.md`
- `docs/DECISIONS.md`
- `docs/HANDOFF.md`
- `docs/LOCAL_LLM_MAPPING_ROADMAP.md`

### Tests run
- `.venv/bin/python -m py_compile scripts/benchmark_mapping_models.py tests/test_benchmark_mapping_models.py` -> passed
- `.venv/bin/python -m pytest tests/test_benchmark_mapping_models.py -q` -> `3 passed`
- `.venv/bin/python -m pytest tests/ -q` -> `347 passed`
- Live harness smoke:
  - `.venv/bin/python scripts/benchmark_mapping_models.py --models gemma4:26b --fixture thai_debit_credit --mode text --run-id smoke --no-markdown` -> passed
- Full harness:
  - `.venv/bin/python scripts/benchmark_mapping_models.py --run-id 20260424-gemma-mapping-fixtures` -> passed

### Decisions made
- Use this script, not ad hoc snippets, for future local model comparisons.
- Keep benchmark artifacts ignored under `artifacts/`; record only summarized outcomes in docs unless a specific artifact must be preserved.

### Warnings
- The harness is not a CI test; it requires local Ollama and installed models.
- Fixtures are synthetic and useful for model comparison, but still need expansion across all 8 supported banks before any stronger automation policy.

### Environment changes
- No dependencies installed by Codex.
- Generated ignored artifacts under `artifacts/llm_mapping_benchmarks/`.

## Done (previous session) — Mapping Assist Fixture Benchmark

### What I changed
- Updated production mapping assist calls in `services/mapping_assist_service.py`:
  - text mapping assist now passes `think=false` and `max_tokens=1024`
  - vision mapping assist now passes `think=false` and `max_tokens=1024`
  - default mapping-assist model is now `gemma4:26b` when `OLLAMA_MAPPING_MODEL` is not set
  - vision mapping assist uses the mapping model default for mapping-specific vision calls instead of falling back to the generic vision role
- Updated `tests/test_mapping_assist_service.py` to assert structured mapping calls use the bounded no-think path and the new default model.
- Ran synthetic task-specific benchmarks against `gemma4:e2b`, `gemma4:e4b`, and `gemma4:26b`.
- Recorded results in `docs/LOCAL_LLM_BENCHMARKS.md`.
- Added `DEC-021` and updated `docs/LOCAL_LLM_MAPPING_ROADMAP.md`.

### Benchmark results
- Fixtures:
  - `thai_debit_credit`
  - `english_signed_amount`
  - `ocr_noisy_signed_amount`
- `gemma4:e2b`:
  - text `14/21` = `66.67%`, avg `4,022.08 ms`
  - vision `3/21` = `14.29%`, avg `4,264.31 ms`
- `gemma4:e4b`:
  - text `15/21` = `71.43%`, avg `7,375.73 ms`
  - vision `15/21` = `71.43%`, avg `7,043.96 ms`
- `gemma4:26b`:
  - text `21/21` = `100%`, avg `8,520.42 ms`
  - vision `21/21` = `100%`, avg `6,688.96 ms`

### Decisions made
- Use `gemma4:26b` as the default mapping-assist model on this machine.
- Keep `gemma4:e4b` as fast fallback, not primary mapping assistant.
- Treat `gemma4:e2b` as triage-only; it is too lossy for evidentiary mapping suggestions.
- Keep all LLM mapping suggestions suggestion-only, validation-gated, and analyst-applied.

### Files changed
- `services/mapping_assist_service.py`
- `tests/test_mapping_assist_service.py`
- `docs/LOCAL_LLM_BENCHMARKS.md`
- `docs/DECISIONS.md`
- `docs/HANDOFF.md`
- `docs/LOCAL_LLM_MAPPING_ROADMAP.md`

### Tests run
- `.venv/bin/python -m py_compile services/mapping_assist_service.py tests/test_mapping_assist_service.py` -> passed
- `.venv/bin/python -m pytest tests/test_mapping_assist_service.py tests/test_llm_service.py -q` -> `9 passed`
- `.venv/bin/python -m pytest tests/ -q` -> `344 passed`
- Live default-model smoke:
  - `suggest_mapping_with_llm(...)` without explicit model used `gemma4:26b`, validation `ok`, mapping complete for Thai debit/credit fixture.

### Warnings
- `gemma4:26b` has higher cold-load cost, but it is materially more accurate on the synthetic mapping fixtures.
- `gemma4:e2b` and `gemma4:e4b` can return valid JSON while still missing important mapping fields; JSON smoke alone is not enough for model selection.
- The extra prompt experiment that explicitly banned sample-row values reduced recall for `e2b/e4b`; it was reverted. Safety still comes from column cleaning, validation, and analyst review.

### Failed attempts / Notes
- Pre-fix production mapping assist could be slow and incomplete because it did not explicitly disable thinking or cap structured output.
- The stricter prompt experiment made smaller Gemma models overly conservative, so it was not kept.

### Environment changes
- No dependencies installed by Codex.
- No model pulls were performed by Codex in this session.

## Done (previous session) — Gemma Variant Follow-up Sweep

### What I changed
- Ran local-only benchmark sweeps after the user installed additional Gemma variants.
- New models found:
  - `gemma4:e2b` (`7fbdbf8f5e45`, 7.2 GB)
  - `gemma4:26b` (`5571076f3d70`, 17 GB)
- Compared `gemma4:e2b`, `gemma4:e4b`, `gemma4:latest`, and `gemma4:26b` with text + vision smoke tests.
- Added a 3-iteration focused sweep for `e2b`, `e4b`, and `26b` to separate cold-load effects from warm latency.
- Recorded results in `docs/LOCAL_LLM_BENCHMARKS.md`.
- Added `DEC-020` and updated `docs/LOCAL_LLM_MAPPING_ROADMAP.md`.

### Benchmark results
- Single-pass Gemma sweep:
  - `gemma4:e2b`: text `ok` `4,389.15 ms`, vision `ok` `757.84 ms`
  - `gemma4:e4b`: text `ok` `6,120.88 ms`, vision `ok` `1,378.78 ms`
  - `gemma4:latest`: text `ok` `577.38 ms`, vision `ok` `994.74 ms`; same ID as `e4b`, warmed by the previous `e4b` call
  - `gemma4:26b`: text `ok` `8,468.53 ms`, vision `ok` `1,858.47 ms`
- Three-iteration focused sweep:
  - `gemma4:e2b`: text avg `1,682.78 ms`, warm text `~0.37s`; vision avg `492.80 ms`, warm vision `~0.37s`
  - `gemma4:e4b`: text avg `2,251.77 ms`, warm text `~0.49s`; vision avg `646.14 ms`, warm vision `~0.48s`
  - `gemma4:26b`: text avg `3,045.11 ms`, warm text `~0.48s`; vision avg `890.70 ms`, warm vision `~0.49s`

### Decisions made
- Keep `gemma4:e4b` as balanced pinned fast fallback for now.
- Treat `gemma4:e2b` as ultra-fast/lightweight triage candidate.
- Treat `gemma4:26b` as higher-quality candidate for the next synthetic mapping/OCR fixture benchmark.
- Do not switch defaults based on JSON smoke latency alone.

### Files changed
- `docs/LOCAL_LLM_BENCHMARKS.md`
- `docs/DECISIONS.md`
- `docs/HANDOFF.md`
- `docs/LOCAL_LLM_MAPPING_ROADMAP.md`

### Tests run
- No code changes in this session.
- Verification was the local Ollama benchmark sweep only; previous code regression baseline remains backend `344 passed`, frontend `37 passed`, frontend build passed.

### Warnings
- `gemma4:latest` currently shares the same ID as `gemma4:e4b`, but must not be used for production-like reproducibility.
- Smoke benchmark only validates JSON compliance and latency. It does not measure mapping accuracy, OCR quality, hallucination resistance, or Thai finance-domain reasoning.

### Failed attempts / Notes
- Single-pass latency is affected by model load/warm state. Use the 3-iteration focused sweep for operational comparison.

### Environment changes
- No dependencies installed by Codex.
- User installed additional Ollama models before this benchmark.

## Done (previous session) — Installed Local LLM Model Sweep

### What I changed
- Hardened `services/llm_service.py` benchmark calls:
  - generated a valid synthetic 1x1 PNG for vision smoke tests
  - capped benchmark output tokens
  - recorded Ollama timeouts as benchmark run status instead of crashing the harness
  - routed explicit `think=false` calls through native Ollama `/api/chat`, because the OpenAI-compatible path can spend the token budget on reasoning before returning final content
- Ran a local-only sweep against every installed Ollama tag:
  - `qwen3.5:9b`
  - `qwen3.6:27b`
  - `qwen3.5:27b`
  - `gemma4:latest`
  - `gemma4:e4b`
- Recorded the sweep in `docs/LOCAL_LLM_BENCHMARKS.md`.
- Added `DEC-019` for native `think=false` benchmarking and installed-model guidance.
- Updated `docs/LOCAL_LLM_MAPPING_ROADMAP.md` with installed-model recommendations.

### Benchmark results
- `gemma4:e4b`:
  - text `ok`, `579.06 ms`
  - vision `ok`, `993.94 ms`
  - best installed fast + vision smoke result; prefer pinned tag over `:latest`, but keep schema validation because text smoke localized field values
- `gemma4:latest`:
  - text `ok`, `6,050.71 ms`
  - vision `ok`, `1,316.14 ms`
  - same local model ID as `gemma4:e4b`, but tag is less reproducible
- `qwen3.5:9b`:
  - text `ok`, `2,558.23 ms`
  - vision `error`, Ollama runner `500`
  - best installed Qwen text candidate
- `qwen3.5:27b`:
  - text `ok`, `19,708.81 ms`
  - vision `error`, Ollama runner `500`
- `qwen3.6:27b`:
  - text `ok`, `30,704.65 ms`
  - vision `error`, Ollama runner `500`

### Files changed
- `services/llm_service.py`
- `tests/test_llm_service.py`
- `docs/LOCAL_LLM_BENCHMARKS.md`
- `docs/DECISIONS.md`
- `docs/HANDOFF.md`
- `docs/LOCAL_LLM_MAPPING_ROADMAP.md`

### Tests run
- Baseline before code changes:
  - `.venv/bin/python -m pytest tests/ -q` -> `344 passed`
- Focused after benchmark hardening:
  - `.venv/bin/python -m py_compile services/llm_service.py tests/test_llm_service.py` -> passed
  - `.venv/bin/python -m pytest tests/test_llm_service.py -q` -> `6 passed`
- Final regression:
  - `.venv/bin/python -m pytest tests/ -q` -> `344 passed`
  - `npm test` in `frontend/` -> `37 passed`
  - `npm run build` in `frontend/` -> passed (Vite large chunk warning only)

### Decisions made
- For installed models right now, use `gemma4:e4b` as fast fallback and provisional vision smoke candidate.
- Use `qwen3.5:9b` for Qwen-family text experiments; do not default to `qwen3.5:27b` or `qwen3.6:27b` for interactive mapping UX.
- Do not use installed Qwen tags for vision on this machine until the Ollama runner `500` issue is resolved.
- Keep `qwen2.5:14b` / `qwen2.5vl:7b` as unverified baseline targets until those tags are installed and benchmarked.

### Warnings
- OpenAI-compatible `/v1/chat/completions` is not reliable for capped `think=false` smoke tests with the installed Qwen thinking models under the BSIE system prompt; use native `/api/chat` when controlling thinking.
- Qwen vision tags advertise vision capability in `ollama show`, but the smoke test fails with runner `500` on this machine.

### Failed attempts / Notes
- Initial all-model sweep through the OpenAI-compatible path returned empty `message.content` for Qwen models after consuming `256`/`512` completion tokens in reasoning.
- Prompt-only `/no_think` did not fix Qwen under the BSIE system prompt; native `think=false` did.

### Environment changes
- No dependencies installed.
- No model pulls were performed by Codex in this session.

## Done (previous session) — Phase 3 Local LLM Benchmark Run

### What I changed
- Ran the local-only LLM benchmark harness against the current Ollama install.
- Recorded benchmark results in `docs/LOCAL_LLM_BENCHMARKS.md`.
- Added `DEC-018`: Benchmark results do not change the configured baseline roles yet.
- Updated the Phase 3 roadmap to show the first live benchmark is recorded and that baseline text/vision models still need install/rerun.

### Benchmark results
- Installed Ollama models at run time:
  - `qwen3.6:27b`
  - `qwen3.5:27b`
  - `gemma4:latest`
  - `gemma4:e4b`
- Default role run:
  - `text` -> `qwen2.5:14b`: model not installed, Ollama 404
  - `fast` -> `gemma4:e4b`: responded in `40,880.92 ms` but strict JSON check failed in that run
  - `vision` -> `qwen2.5vl:7b`: model not installed, Ollama 404
- Installed-model override run:
  - `text` -> `qwen3.6:27b`: JSON valid, `105,522.48 ms`
  - `fast` -> `gemma4:e4b`: JSON valid, `14,392.83 ms`

### Files changed
- `docs/LOCAL_LLM_BENCHMARKS.md`
- `docs/DECISIONS.md`
- `docs/HANDOFF.md`
- `docs/LOCAL_LLM_MAPPING_ROADMAP.md`

### Tests run
- Baseline before docs update:
  - `.venv/bin/python -m pytest tests/ -q` -> `344 passed`
  - `npm test` in `frontend/` -> `37 passed`

### Decisions made
- Keep the configured role defaults unchanged for now; do not switch text default to installed `qwen3.6:27b` because it is too slow for interactive mapping UX.
- Do not promote `gemma4:e4b` to primary mapping model based on a single run because JSON compliance varied.

### Warnings
- `qwen2.5:14b` and `qwen2.5vl:7b` are not currently installed in Ollama.
- Vision mapping assist live use still requires a vision-capable local model.
- Next benchmark should rerun after pulling the intended baseline models.

### Failed attempts / Notes
- Default benchmark run was `partial` because baseline text/vision models were missing.

### Environment changes
- No dependencies installed.
- No model pulls were performed.

## Done (previous session) — Phase 3 OCR/Vision Mapping Assist

### What I changed
- Added OCR/vision mapping assist for PDF/image uploads.
- Added `MappingVisionAssistRequest` with required `file_id`.
- Added `suggest_mapping_with_vision_llm(...)` in `services/mapping_assist_service.py`:
  - loads the original evidence file from the stored path
  - uses the first PDF page or image bytes as local vision context
  - sends OCR/extracted columns, sample rows, detected bank context, and current mapping
  - requires JSON output
  - drops invented/nonexistent columns
  - repairs debit/credit vs signed amount conflicts
  - validates the merged mapping before returning it
  - returns `suggestion_only=true` and `auto_pass_eligible=false`
- Added `POST /api/mapping/assist/vision` in `routers/ingestion.py`.
- The endpoint resolves files by `file_id` only, rejects stored paths outside `EVIDENCE_DIR`, and does not accept arbitrary client paths.
- Added frontend `assistVisionMapping(...)` API client.
- Added Step 2 `Ask Vision` action for PDF/image uploads only.
- Updated English/Thai i18n strings and regression coverage.

### Files changed
- `persistence/schemas.py`
- `services/mapping_assist_service.py`
- `routers/ingestion.py`
- `frontend/src/api.ts`
- `frontend/src/components/steps/Step2Map.tsx`
- `frontend/src/components/steps/Step2Map.test.tsx`
- `frontend/src/App.workflow.test.tsx`
- `frontend/src/locales/en.json`
- `frontend/src/locales/th.json`
- `tests/test_mapping_assist_service.py`
- `tests/test_app_api.py`
- `docs/DECISIONS.md`
- `docs/HANDOFF.md`
- `docs/LOCAL_LLM_MAPPING_ROADMAP.md`

### Tests run
- Baseline before changes:
  - `.venv/bin/python -m pytest tests/ -q` -> `341 passed`
  - `npm test` in `frontend/` -> `36 passed`
- Focused after changes:
  - `.venv/bin/python -m py_compile services/mapping_assist_service.py routers/ingestion.py persistence/schemas.py tests/test_mapping_assist_service.py tests/test_app_api.py` -> passed
  - `.venv/bin/python -m pytest tests/test_mapping_assist_service.py tests/test_app_api.py -q` -> `51 passed`
  - `npm test -- --run src/components/steps/Step2Map.test.tsx src/App.workflow.test.tsx` -> `10 passed`
- Final verification:
  - `git diff --check` -> passed
  - `.venv/bin/python -m pytest tests/ -q` -> `344 passed`
  - `npm test` in `frontend/` -> `37 passed`
  - `npm run build` in `frontend/` -> passed, Vite large chunk warning only

### Decisions made
- Added `DEC-017`: OCR/vision mapping assist reads evidence by file_id and remains suggestion-only.
- Vision assist is analyst-requested only; it is not run automatically during upload and does not create new columns or rows.

### Warnings
- Requires local Ollama plus a vision-capable model for live use.
- Only the first PDF page is used as the vision preview in this slice.
- OCR repair and row extraction are still future work; this only helps map existing OCR/extracted columns.
- No auto-pass behavior was added.

### Failed attempts / Notes
- None in this slice.

### Environment changes
- No dependencies installed.

## Done (previous session) — Phase 3 Local LLM Benchmark Harness

### What I changed
- Added a local-only benchmark harness for configured Ollama model roles.
- Added `benchmark_llm_roles(...)` in `services/llm_service.py`:
  - uses a fixed synthetic prompt only
  - disables DB auto-context
  - supports `text`, `fast`, and optional `vision` roles
  - records latency, JSON validity, token counts, and short response previews
  - returns structured `offline` / `partial` results when local Ollama or model JSON output is not ready
  - does not persist benchmark results or touch evidence data
- Added `POST /api/llm/benchmark` in `routers/llm.py`.
- Added frontend API helper `benchmarkLlm(...)` for future UI use.
- Added service and API regression tests.
- Updated roadmap and decision log.

### Files changed
- `services/llm_service.py`
- `routers/llm.py`
- `frontend/src/api.ts`
- `tests/test_llm_service.py`
- `tests/test_app_api.py`
- `docs/DECISIONS.md`
- `docs/HANDOFF.md`
- `docs/LOCAL_LLM_MAPPING_ROADMAP.md`

### Tests run
- Baseline before changes:
  - `.venv/bin/python -m pytest tests/ -q` -> `336 passed`
  - `npm test` in `frontend/` -> `36 passed`
- Focused after changes:
  - `.venv/bin/python -m py_compile services/llm_service.py routers/llm.py tests/test_llm_service.py tests/test_app_api.py` -> passed
  - `.venv/bin/python -m pytest tests/test_llm_service.py tests/test_app_api.py -q` -> `52 passed`
  - `npm test -- --run src/App.workflow.test.tsx` -> `2 passed`
- Final verification:
  - `git diff --check` -> passed
  - `.venv/bin/python -m pytest tests/ -q` -> `341 passed`
  - `npm test` in `frontend/` -> `36 passed`
  - `npm run build` in `frontend/` -> passed, Vite large chunk warning only

### Decisions made
- Added `DEC-016`: Local LLM benchmark uses synthetic prompts only.
- Benchmarking is runtime-only and non-persistent; real machine measurements still require local Ollama models to be installed.

### Warnings
- Live benchmark calls require local Ollama to be running.
- Vision benchmark is optional because it requires a local vision-capable model.
- No evidence rows, uploads, parser runs, or mappings are touched by the benchmark path.

### Failed attempts / Notes
- Accidentally tried `python -m py_compile`, but this shell has no `python` binary; reran successfully with `.venv/bin/python`.

### Environment changes
- No dependencies installed.

## Done (previous session) — Phase 3 Local LLM Model Role Config

### What I changed
- Added centralized local Ollama model role config in `services/llm_service.py`.
- Added role defaults:
  - text: `OLLAMA_TEXT_MODEL` / fallback `qwen2.5:14b`
  - vision: `OLLAMA_VISION_MODEL` / fallback `qwen2.5vl:7b`
  - fast: `OLLAMA_FAST_MODEL` / fallback `gemma4:e4b`
  - mapping override: `OLLAMA_MAPPING_MODEL`
- Added `resolve_model(...)` and `get_llm_model_config()`.
- Text chat, summarization, classification, and Excel/text file analysis now default to the text role.
- Image/PDF file analysis now defaults to the vision role.
- `/api/llm/status` now returns non-secret model role config for UI/debug visibility.
- Updated the LLM chat UI to display the configured text model when status returns role config.
- Updated `.env.example`, roadmap, decision log, and regression coverage.

### Files changed
- `.env.example`
- `services/llm_service.py`
- `services/mapping_assist_service.py`
- `routers/llm.py`
- `frontend/src/components/LlmChat.tsx`
- `tests/test_llm_service.py`
- `docs/DECISIONS.md`
- `docs/HANDOFF.md`
- `docs/LOCAL_LLM_MAPPING_ROADMAP.md`

### Tests run
- Baseline before changes:
  - `.venv/bin/python -m pytest tests/ -q` -> `334 passed`
  - `npm test` in `frontend/` -> `36 passed`
- Focused after changes:
  - `.venv/bin/python -m pytest tests/test_llm_service.py tests/test_mapping_assist_service.py tests/test_app_api.py -q` -> `49 passed`
  - `npm test -- --run src/App.workflow.test.tsx` -> `2 passed`
- Final verification:
  - `.venv/bin/python -m pytest tests/ -q` -> `336 passed`
  - `npm test` in `frontend/` -> `36 passed`
  - `npm run build` in `frontend/` -> passed, Vite large chunk warning only

### Decisions made
- Added `DEC-015`: Local Ollama endpoints resolve models by role.
- Explicit per-request model overrides still work; empty/default frontend requests now resolve through the centralized local role config.

### Warnings
- Requires local Ollama to be running for live use.
- Model names are defaults only; the operator still needs to pull/install the configured Ollama models locally.
- No auto-pass behavior was added.

### Failed attempts / Notes
- None in this slice.

### Environment changes
- No dependencies installed.
- `.env.example` now documents optional local Ollama variables.

## Done (previous session) — Phase 3 Local LLM Mapping Assist

### What I changed
- Added guarded local LLM mapping assist for Step 2.
- Added `services/mapping_assist_service.py`:
  - sends only safe structured mapping context to local Ollama
  - requires JSON output
  - drops invented/nonexistent columns
  - repairs debit/credit vs signed amount conflicts
  - validates the merged mapping before returning it
  - always returns `suggestion_only=true` and `auto_pass_eligible=false`
- Added `POST /api/mapping/assist` in `routers/ingestion.py`.
- Added frontend `assistMapping(...)` API client.
- Added Step 2 UI panel for Local LLM Mapping Assist:
  - request suggestion
  - show confidence/model/reasons/warnings/validation status
  - apply suggestion only after explicit analyst click
  - does not bypass bank/mapping review gates
- Added English/Thai i18n strings and regression coverage.

### Files changed
- `services/mapping_assist_service.py`
- `persistence/schemas.py`
- `routers/ingestion.py`
- `frontend/src/api.ts`
- `frontend/src/components/steps/Step2Map.tsx`
- `frontend/src/components/steps/Step2Map.test.tsx`
- `frontend/src/App.workflow.test.tsx`
- `frontend/src/locales/en.json`
- `frontend/src/locales/th.json`
- `tests/test_mapping_assist_service.py`
- `tests/test_app_api.py`
- `docs/DECISIONS.md`
- `docs/HANDOFF.md`
- `docs/LOCAL_LLM_MAPPING_ROADMAP.md`

### Tests run
- Baseline before changes:
  - `.venv/bin/python -m pytest tests/ -q` -> `331 passed`
  - `npm test` in `frontend/` -> `35 passed`
- Focused after changes:
  - `.venv/bin/python -m pytest tests/test_mapping_assist_service.py tests/test_app_api.py -q` -> `47 passed`
  - `npm test -- --run src/components/steps/Step2Map.test.tsx src/App.workflow.test.tsx` -> `9 passed`
- Final verification:
  - `.venv/bin/python -m pytest tests/ -q` -> `334 passed`
  - `npm test` in `frontend/` -> `36 passed`
  - `npm run build` in `frontend/` -> passed, Vite large chunk warning only

### Decisions made
- Added `DEC-014`: Local LLM mapping assist is suggestion-only and validation-gated.
- LLM output is never auto-applied; Step 2 requires an analyst action to apply the suggestion as a draft mapping.

### Warnings
- Requires local Ollama to be running for live use. Offline Ollama returns an error and leaves the mapping unchanged.
- This first slice is text/Excel-context oriented. OCR/vision mapping assist remains future work.
- No auto-pass behavior was added.

### Failed attempts / Notes
- None yet in this slice.

### Environment changes
- No new dependencies installed.

## Done (previous session) — Phase 2 Variant Review/Admin UI

### What I changed
- Pushed the existing two commits on `Smarter-BSIE` to `origin/Smarter-BSIE`.
- Added frontend API clients for:
  - `GET /api/mapping/variants`
  - `POST /api/mapping/variants/{variant_id}/promote`
- Added a per-bank `Template Variants` panel inside `BankManager`.
- The panel lets analysts/admins:
  - list variants for the selected bank
  - filter by trust state
  - inspect source type, sheet/header, columns, mapped fields, dry-run valid rows, confirmations, correction rate, reviewer count, and update time
  - promote `candidate -> verified` and `verified -> trusted`
  - attach a promotion note
- Promotion buttons use the current sidebar operator name and are disabled for anonymous/default `analyst`, matching backend named-reviewer guardrails.
- Added English/Thai i18n keys and a regression test for variant listing + promotion.

### Files changed
- `frontend/src/api.ts`
- `frontend/src/components/BankManager.tsx`
- `frontend/src/components/BankManager.test.tsx`
- `frontend/src/locales/en.json`
- `frontend/src/locales/th.json`
- `docs/DECISIONS.md`
- `docs/HANDOFF.md`
- `docs/LOCAL_LLM_MAPPING_ROADMAP.md`

### Tests run
- Baseline before changes:
  - `.venv/bin/python -m pytest tests/ -q` -> `331 passed`
  - `npm test` in `frontend/` -> `34 passed`
- Focused after changes:
  - `npm test -- --run src/components/BankManager.test.tsx` -> `2 passed`
  - `npm run build` in `frontend/` -> passed, Vite large chunk warning only
- Final verification:
  - `.venv/bin/python -m pytest tests/ -q` -> `331 passed`
  - `npm test` in `frontend/` -> `35 passed`
  - `npm run build` in `frontend/` -> passed, Vite large chunk warning only

### Decisions made
- Added `DEC-013`: Variant admin UI exposes staged promotion only.
- Variant promotion UI is staged only: `candidate -> verified -> trusted`. Direct UI promotion from candidate to trusted is intentionally not exposed even though the backend endpoint can accept higher target states.
- Promotion remains named-reviewer gated in the UI to mirror backend enforcement and preserve review accountability.

### Warnings
- The UI is per selected bank in Bank Manager; there is not yet a global all-bank variant queue.
- This UI still does not enable auto-pass. It only manages the trust lifecycle used by the guarded suggestion path.

### Failed attempts / Notes
- Initial BankManager regression test asserted variant text before the async variants query rendered; the test now waits for the variant row.

### Environment changes
- No new dependencies installed.

## Done (previous session) — Phase 2 Gated Variant Suggestions

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
- Frontend admin/review UI was added in the next session inside Bank Manager.

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
