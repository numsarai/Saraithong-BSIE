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

### DEC-046: Scoped classification preview requires analyst row selection
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** DEC-045 allowed the preview endpoint to accept a broad supported scope directly, but a one-click scoped preview can still hide which persisted rows were sent to the local model. For evidence-sensitive review, the UI should show the deterministic transaction set first and make row selection explicit.
- **Decision:** The AI Copilot Evidence UI now loads persisted transactions from the current `parser_run_id`, `file_id`, or `account` scope through `/api/transactions/search`, displays them in a bounded picker, and sends only analyst-selected rows to `POST /api/llm/classification-preview` as explicit `transactions`. The backend scoped-preview contract remains available for compatibility, but the primary UI path is load -> select -> preview.
- **Alternatives:** (1) Keep `Preview From Scope` as a direct LLM call -- faster, but less transparent about the exact rows used. (2) Require manual copy/paste forever -- transparent but tedious and error-prone. (3) Add an apply workflow immediately -- premature without explicit audit and review-history semantics.
- **Consequences:** Analysts can inspect the exact transaction ids, dates, amounts, descriptions, and current types before involving the local model. Preview remains read-only and unaudited because no evidence changes occur; any future apply path must add analyst confirmation, audit logging, and review history.

### DEC-045: Classification preview can load scoped persisted transactions
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** DEC-044 added a read-only manual classification preview, but manually copying transaction fields is too error-prone for actual investigator review. The preview needs to inspect persisted transactions from the same evidence scope controls already used by Evidence Copilot while still avoiding any writes or hidden broad database access.
- **Decision:** Extend `POST /api/llm/classification-preview` so callers may provide either explicit `transactions` or a supported scope (`parser_run_id`, `file_id`, `account`) plus `max_transactions`. Scoped preview queries persisted transactions through the existing search serialization path, normalizes account input to digits for account matching, caps rows at 25, then sends those bounded rows through the same local-only preview contract. Case tags remain unsupported for classification preview until a dedicated case-tag-to-transaction review policy is designed.
- **Alternatives:** (1) Force users to copy/paste fields from result tables -- safe but clumsy and likely to introduce transcription errors. (2) Let the LLM query arbitrary database context -- too broad and unauditable. (3) Support case tags immediately -- useful later, but tags can point to mixed object types and need a clearer transaction selection policy first.
- **Consequences:** Analysts can preview local classification suggestions over real scoped evidence without mutating records. Future apply/review workflows can build on the same scoped transaction retrieval, but must add explicit analyst confirmation and audit logging before changing persisted classification.

### DEC-044: Classification preview is read-only and local-only
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** DEC-043 made optional classification enrichment local-first, but enabling broad automatic overrides without a preview/review surface would still be too abrupt for evidence-sensitive workflows. Investigators need a way to compare heuristic/current classification against local model suggestions before any future apply path exists.
- **Decision:** Add `POST /api/llm/classification-preview` as a read-only local-only preview endpoint. It accepts bounded analyst-provided transaction rows, calls the local classification provider even when the pipeline-wide `BSIE_ENABLE_LLM_CLASSIFICATION` flag is off, and returns current classification, AI suggestion, suggested preview result, review requirement, action, reason, model, and warnings. The endpoint never writes records, never applies overrides, and exposes `read_only=true` / `mutations_allowed=false`. The AI Copilot Evidence UI includes a compact manual preview form so analysts can test one transaction at a time.
- **Alternatives:** (1) Enable the pipeline enrichment flag and inspect output packages -- too coarse and can change processing results while testing. (2) Add an apply button immediately -- premature before review/audit semantics are designed. (3) Put this in generic project chat -- weaker contract and less clear that it is a local-only classification preview.
- **Consequences:** Analysts can evaluate local model behavior safely before rollout. A future apply workflow must add explicit analyst confirmation, audit logging, and persisted review history rather than reusing this preview endpoint as a mutation path.

### DEC-043: Optional AI classification enrichment is local-first
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** The transaction classification pipeline already had a guarded optional LLM enrichment step, but the enabled path still depended on `LLM_API_KEY` and the legacy OpenAI helper. That conflicted with the current local-only operating mode and made it too easy for classified bank-statement data to leave the machine if someone enabled the flag with an API key present.
- **Decision:** Keep heuristic classification as the default and keep `BSIE_ENABLE_LLM_CLASSIFICATION=0` by default. When optional AI enrichment is enabled, `services/classification_service.py` now defaults to `BSIE_CLASSIFICATION_LLM_PROVIDER=local`, calls local Ollama `/api/chat` with `think=false` and JSON output, and uses `OLLAMA_CLASSIFICATION_MODEL` with `OLLAMA_TEXT_MODEL` / `OLLAMA_DEFAULT_MODEL` fallback. The local path sends bounded normalized transaction fields only, accepts only known transaction ids and allowlisted transaction types, clamps confidence, and fails closed to heuristic values when Ollama is unavailable, times out, or returns invalid JSON. The legacy OpenAI helper remains reachable only through explicit `legacy_openai` provider selection plus `LLM_API_KEY`.
- **Alternatives:** (1) Remove the legacy helper immediately -- cleaner, but risks breaking older local test harnesses or one-off migration work. (2) Keep `LLM_API_KEY` as the main gate -- simple, but not local-first and unsafe for classified evidence. (3) Let Copilot classify transactions interactively -- violates the read-only copilot contract and weakens deterministic review gates.
- **Consequences:** AI classification enrichment can now run self-hosted when deliberately enabled, while heuristic classification remains the evidence-preserving baseline. Invalid local model output cannot invent transaction ids or unsupported types into normalized evidence. Future work can add an analyst-facing review surface before enabling broader automatic type overrides.

### DEC-042: Evidence Copilot supports case tag scope through linked evidence objects
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** Evidence Copilot could already scope answers by parser run, file, or account, but investigators often organize related records with case tags. Without case-tag scope, an analyst would need to copy multiple lower-level ids into the prompt manually, increasing the chance of over-broad or under-scoped answers.
- **Decision:** Extend `copilot_scope` with `case_tag_id` and `case_tag`. The backend resolves the tag through `case_tags` / `case_tag_links`, treats the tag as a scope filter rather than a citation target, and narrows transactions through linked files, parser runs, accounts, transactions, and alerts. Id/name mismatches fail closed, unknown tags return not found, and empty tags produce a structured warning with no matching transactions. The Evidence UI exposes a searchable case-tag picker with linked-object counts, linked-object detail/navigation, and manual fallback fields while preserving the existing citation/audit contract.
- **Alternatives:** (1) Let the LLM interpret tag names in free text -- unsafe and not auditable. (2) Add a separate case-tag endpoint for copilot -- clearer but duplicates the existing scope/citation/audit path. (3) Wait for a richer case picker UI first -- nicer UX, but backend scope safety is the higher-priority contract.
- **Consequences:** Analysts can ask Evidence Copilot questions over tagged evidence groups without giving it access outside the project database. Case tags remain organizational filters; answers should cite the linked underlying records (`txn`, `alert`, `run`, `file`, or `account`) rather than citing the tag itself.

### DEC-041: Evidence Copilot graph metrics are deterministic scoped aggregates
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** Evidence Copilot can cite transactions, alerts, and review history, but account-summary and report-draft tasks also need network shape: number of counterparties, directional degree, inbound/outbound flow, and top flow edges. Rebuilding full graph export artifacts for each chat request would be heavier than necessary for an interactive read-only context pack.
- **Decision:** Add `evidence.graph_metrics` to the deterministic copilot context pack as bounded SQL aggregates over normalized transactions matching the current `copilot_scope`. Metrics include transaction-edge count, unique counterparties, inbound/outbound counterparty counts, directional degree, flow in/out counts and values, net/total flow, per-account metrics, and top flow edges already derived from scoped counterparties. The prompt instructs the model to cite scoped account ids and supporting transaction ids when discussing these metrics.
- **Alternatives:** (1) Call the full graph export/analysis pipeline per copilot request -- richer but heavier and unnecessary for the first interactive slice. (2) Let the LLM infer network shape from top transactions -- unsafe and incomplete. (3) Wait for case-tag scope first -- useful later, but scoped parser run/file/account metrics already add value now.
- **Consequences:** Evidence Copilot can answer network-shape questions from deterministic scoped aggregates without mutating evidence. These are summary metrics, not a replacement for full graph exports, SNA, or i2 artifacts.

### DEC-040: Evidence Copilot context includes scoped review and audit history
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** Evidence Copilot task modes can now ask for review checklists and report drafts, but the deterministic context pack only included files, parser runs, accounts, transactions, counterparties, and alerts. That meant the assistant could not distinguish raw extracted evidence from analyst-reviewed or corrected records.
- **Decision:** Enrich the deterministic copilot context pack with a bounded `review_history` section built from `review_decisions` and `audit_logs` for the scoped file/run, scoped accounts, scoped alerts, and included top transactions. Review/audit entries carry a `citation_id` pointing back to the underlying `txn`, `account`, `file`, `run`, or `alert` record; the prompt instructs the model to cite that underlying evidence id when discussing review history.
- **Alternatives:** (1) Let the LLM inspect the whole audit log -- too broad and not scope-safe. (2) Add a new citation type for audit events immediately -- larger contract change and not necessary while the reviewed object already has an evidence id. (3) Keep review history out until a review-specific UI exists -- weakens the current review checklist task.
- **Consequences:** Evidence Copilot can now mention prior analyst corrections/review decisions from scoped context without mutating records or using hidden data. The history is intentionally bounded to avoid huge prompts; future work can add case-level review history once case tag scope exists.

### DEC-039: Evidence Copilot task modes are backend-owned prompt contracts
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** The unified AI Copilot workspace exposed Evidence mode, but its presets were still frontend prompt text. That made important investigation workflows depend on UI copy instead of a testable backend contract.
- **Decision:** Add a `task_mode` field to `POST /api/llm/copilot` with backend-owned modes: `account_summary`, `alert_explanation`, `review_checklist`, and `draft_report_paragraph`, while keeping `freeform` for backward-compatible scoped questions. The backend injects task instructions into the prompt, records `task_mode` in audit context and responses, preserves explicit scope/citations/context hash, and still rejects unknown modes. The frontend now selects task modes and sends optional analyst focus text instead of storing the main task prompt in UI strings.
- **Alternatives:** (1) Keep quick prompt buttons only in the frontend -- faster, but the task behavior is not auditable as a contract. (2) Create separate endpoints per task -- clearer names, but duplicates the scope/citation/audit path. (3) Let the LLM infer the task from the question -- weaker reproducibility and harder to test.
- **Consequences:** Evidence Copilot workflows are now easier to regression-test and evolve. Future task modes should be added in the backend first, with tests for read-only behavior, citations, and audit metadata before UI exposure.

### DEC-038: AI Copilot unifies project chat and evidence-scoped investigation modes
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** The operator preferred one AI workspace instead of separate `AI Analysis` and `Copilot` tabs. At the same time, even non-evidence AI chat must remain bounded to BSIE/project work rather than becoming a general-purpose assistant.
- **Decision:** Keep the backend contracts separate (`/api/llm/chat` for project-scoped local chat and `/api/llm/copilot` for citation/audit-bound evidence work), but expose them together in one Investigation Desk tab named `AI Copilot`. The tab has `Project` and `Evidence` modes. Project mode uses the existing local chat path with an explicit BSIE-only system guardrail, while Evidence mode uses the scoped read-only copilot contract from DEC-036.
- **Alternatives:** (1) Keep separate tabs as in DEC-037 -- clear separation, but creates an artificial UX split. (2) Merge everything into `/api/llm/chat` -- simpler UI, but weakens citations, scope requirements, and audit continuity for evidence answers. (3) Force every AI prompt through `/api/llm/copilot` -- too strict for project/workflow questions that do not have a specific evidence scope.
- **Consequences:** Analysts see one AI entry point, but the evidence-sensitive path still requires explicit scope and records citation/audit metadata. Generic local chat is no longer general-purpose; it should refuse questions outside BSIE, bank-statement processing, Thai financial investigation workflows, supported evidence files, local LLM usage in BSIE, or explicitly provided project context.

### DEC-037: Investigation copilot UI remains scoped and separate from generic AI chat
- **Date:** 2026-04-24
- **Status:** superseded by DEC-038
- **Context:** BSIE already has a generic local AI analysis tab, but Phase 4 investigation copilot has stronger evidence requirements: explicit scope, read-only behavior, citations, and audit continuity. Mixing those flows in one chat surface would make it easy to ask unscoped questions by accident.
- **Decision:** Add a dedicated Copilot tab inside Investigation Desk that calls only `POST /api/llm/copilot`. The panel exposes `parser_run_id`, `file_id`, and `account` scope fields, quick scope-fill buttons from selected investigation context, bounded transaction count, and answer metadata including status, citation policy, context hash, audit id, and citations.
- **Alternatives:** (1) Reuse `LlmChat` for copilot prompts -- faster but preserves auto-context/general-chat mental model. (2) Put copilot inside Link Chart first -- too narrow for file/run/account review workflows. (3) Hide scope fields and infer everything from current UI state -- convenient but weaker for auditability.
- **Consequences:** The generic AI tab remains available for broad local LLM use, while investigation copilot is visibly scoped and evidence-cited. Future task modes should build on this panel without bypassing the backend scope/citation/audit contract.

### DEC-036: Investigation copilot starts with read-only scoped context packs
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** Phase 4 needs local LLM help inside analyst workflows, but a copilot that can read outside the selected evidence set, rely on auto-context, or answer without record-level citations would weaken evidentiary integrity.
- **Decision:** Start investigation copilot with a single read-only backend path: `POST /api/llm/copilot`. The endpoint requires a `copilot_scope` with `parser_run_id`, `file_id`, or `account`, builds a deterministic context pack from DB records, calls the local text model with `auto_context=false`, and records an audit log with operator, model, context hash, prompt hash, and response status. Responses expose citation ids and flag missing-citation answers as `needs_review`.
- **Alternatives:** (1) Extend generic `/api/llm/chat` with implicit DB context -- too broad and hard to audit. (2) Build a frontend copilot panel first -- attractive, but unsafe before backend scope/citation/audit contracts exist. (3) Let the LLM query tools dynamically -- too much autonomy for the first evidence-sensitive slice.
- **Consequences:** Phase 4 begins with a narrow contract that can support account summaries, alert explanations, review checklists, and report drafting later. The copilot cannot mutate evidence, classify transactions, promote mappings, review alerts, or create findings.

### DEC-035: Qwen 2.5 baseline models are retired from the local LLM roadmap
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** The operator has ruled out `qwen2.5:14b` and `qwen2.5vl:7b` as realistic candidates for the current BSIE local LLM plan. Installed-model and task-specific benchmark work has already moved the practical mapping path to Gemma/Qwen 3.5 candidates, while keeping Qwen 2.5 install/rerun tasks would waste time and confuse future agents.
- **Decision:** Remove `qwen2.5:14b` and `qwen2.5vl:7b` from future model-selection and benchmark roadmaps. Historical benchmark rows may stay as history only. Runtime text fallback moves to `qwen3.5:9b`; runtime vision fallback moves to `gemma4:e4b`; current mapping assist remains on `gemma4:26b`.
- **Alternatives:** (1) Install the Qwen 2.5 models just to complete the old baseline comparison -- no longer useful for the operator's decision. (2) Leave them as unverified baseline candidates -- keeps a stale blocker in Phase 3. (3) Use floating `:latest` tags instead -- not reproducible enough for evidence-sensitive flows.
- **Consequences:** Phase 3 no longer has a Qwen 2.5 benchmark blocker. The next LLM work should move to Phase 4 copilot scope/citation/audit design or new non-Qwen-2.5 candidates if needed.

### DEC-034: OCR account presence locations preserve bounding boxes for evidence overlays
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** Step 2 could show OCR match centers on image evidence, but center dots are weaker than the OCR text box lineage already produced by EasyOCR. The OCR loader preserves full token `bbox` coordinates, but account-presence results did not expose them.
- **Decision:** Carry OCR token bounding boxes through account-presence match locations as `ocr_bbox` and use them in the Step 2 evidence preview drawer to draw a rectangular overlay on image evidence. If no valid bbox is present, fall back to the existing center-point marker.
- **Alternatives:** (1) Keep center markers only -- usable but less precise. (2) Recompute OCR boxes in the frontend -- not acceptable and duplicates evidence extraction. (3) Ask a vision model to locate the account text -- non-deterministic and unnecessary when EasyOCR already returned coordinates.
- **Consequences:** Investigators can see the exact OCR text region behind an account-presence match on images. PDF/table/page-text matches still use textual page/row/column lineage until a separate PDF coordinate extraction path exists.

### DEC-033: Evidence preview opens only stored PDF/image evidence by file_id
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** Step 2 account-presence review can now show page/table/OCR-token locations, but investigators also need a safe way to open the original stored evidence from those location cards. Serving arbitrary stored paths would weaken evidence-storage confinement.
- **Decision:** Add an inline evidence preview endpoint at `/api/files/{file_id}/evidence-preview` that resolves the file through the database record, validates a UUID-style `file_id`, confines the resolved path to `EVIDENCE_DIR`, and serves only PDF/image file types (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.bmp`). Step 2 location cards link to this endpoint and include a PDF `#page=N` fragment when page lineage is available.
- **Alternatives:** (1) Expose stored filesystem paths in the UI -- not acceptable for classified evidence handling. (2) Reuse export download endpoints -- those are account/output oriented and not scoped to stored source evidence. (3) Build a full region-highlighting document viewer immediately -- useful but larger than the current safe preview need.
- **Consequences:** Analysts can jump from a deterministic account-presence match to the source PDF/image in a new browser tab. Excel evidence still shows row/column locations only; richer spreadsheet previews can be added separately.

### DEC-032: Frontend workflow steps are lazy-loaded to keep the main bundle small
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** Vite reported a large bundle because the main app imported every workflow step eagerly. `Step5Results` pulls graph/chart runtime dependencies through `AccountFlowGraph`, `TimelineChart`, `TimeWheel`, and related result views, so the initial app chunk carried code that is only needed after upload/mapping/configuration.
- **Decision:** Lazy-load `Step1Upload` through `Step5Results` from `frontend/src/App.tsx` while keeping the existing lazy page boundaries for Dashboard, Bank Manager, Bulk Intake, and Investigation Desk. Raise Vite's `chunkSizeWarningLimit` to `900` because the remaining large chunk is the intentionally isolated Cytoscape graph runtime rather than the initial app bundle.
- **Alternatives:** (1) Leave eager workflow imports and ignore the warning -- keeps the startup bundle unnecessarily large. (2) Disable all chunk warnings -- hides future regressions. (3) Hand-roll deeper graph library splitting now -- higher implementation risk for a known lazy chunk that no longer blocks first load.
- **Consequences:** The initial app chunk dropped from about `1,209 kB` to about `360 kB`; Cytoscape remains a lazy graph chunk at about `803 kB`. Tests that interact with the upload workflow must wait for lazy-rendered step content before querying step-specific elements.

### DEC-031: OCR account presence scans raw accepted text tokens
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** OCR table reconstruction can drop header/free-text account numbers that do not cluster into a transaction table. That made image/scanned-PDF account presence weaker than text PDF page scanning even when EasyOCR had detected the account text.
- **Decision:** Preserve accepted OCR text boxes as `ocr_tokens` from `core.image_loader.parse_image_file`, including page number, confidence, bounding box, and text. Account-presence verification now scans both OCR table cells and raw OCR tokens, reporting `source_region=ocr_token` and `ocr_tokens_scanned` in the summary. Low-confidence OCR boxes remain filtered by the existing EasyOCR threshold.
- **Alternatives:** (1) Only scan reconstructed OCR tables — misses header/free-text account numbers. (2) Lower OCR confidence thresholds for account verification — increases false-positive risk. (3) Ask a vision model to locate account text — non-deterministic and unnecessary when EasyOCR already returns tokens.
- **Consequences:** Account numbers in OCR header/free text can be found without LLM inference. OCR token scanning still depends on EasyOCR availability and confidence; unavailable OCR remains warning-only rather than `not_found`.

### DEC-030: Account presence verification extends to text PDF and OCR tables fail-closed
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** Account-presence verification initially covered Excel only, but Step 2 already accepts stored PDF/image evidence. Investigators need the same explicit account check on text PDFs and OCR-derived tables without asking an LLM to infer whether an account appears.
- **Decision:** Extend `/api/mapping/account-presence` to scan text-based PDF page text, extracted PDF tables, and OCR table cells from image/scanned-PDF parsing. The verifier reports source regions (`page_text`, `pdf_table`, `ocr_table`), page/table locations, OCR usage, and search-unit counts. If OCR is unavailable or produces no searchable table cells, return structured warning statuses (`read_error` or `no_searchable_text`) instead of claiming the account is absent.
- **Alternatives:** (1) Keep the endpoint Excel-only — leaves PDF/image workflows without deterministic account review. (2) Use vision LLM output to decide presence — non-reproducible and unsafe for evidence checks. (3) Treat OCR dependency failures as `not_found` — too strict because unavailable OCR is not evidence of absence.
- **Consequences:** Text PDFs and OCR table outputs can now participate in the same Step 2 account review gate when a deterministic scan returns `not_found` or `possible_leading_zero_loss`. OCR-unavailable and no-searchable-text cases stay warning-only until better extraction coverage exists.

### DEC-029: Negative account presence verification requires analyst confirmation
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** Excel account-presence verification can now distinguish `exact_found`, `not_found`, and `possible_leading_zero_loss`. A selected account that is absent from the workbook, or only appears as a possible leading-zero-loss candidate, is evidence-relevant uncertainty and should not pass Step 2 silently.
- **Decision:** Treat `not_found` and `possible_leading_zero_loss` account-presence results as account review blockers in Step 2. The analyst must explicitly confirm the known account before continuing to configuration. `exact_found` remains auto-cleared, while unsupported/read-error style statuses remain visible warnings until deterministic PDF/image/OCR verification policy exists.
- **Alternatives:** (1) Block every unverified account — too strict for PDF/image sources until equivalent verification exists. (2) Warn only and allow pipeline continuation — hides evidence uncertainty behind a non-blocking UI message. (3) Ask the LLM to decide whether the account is acceptable — unsafe and non-reproducible.
- **Consequences:** Workbook account mismatches and leading-zero risk now use the same explicit analyst gate as known account overrides. Confirmation remains auditable through the mapping confirmation context, and exact workbook matches still avoid unnecessary friction.

### DEC-028: Account presence verification scans stored workbook evidence deterministically
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** After moving known subject account context into Step 2, BSIE still needed a deterministic way to check whether that account appears in the stored workbook evidence before processing. Relying only on identity inference or sample rows can miss accounts in pre-header text, other columns, or later rows.
- **Decision:** Add a local-only `/api/mapping/account-presence` endpoint backed by deterministic Excel workbook scanning. The endpoint resolves evidence by `file_id`, confines reads to evidence storage, scans raw worksheet cells with `header=None`, reports exact locations and possible leading-zero-loss candidates, and returns structured unsupported status for non-Excel sources. Step 2 exposes this as an explicit analyst action and passes the result into mapping assist and confirmation audit context.
- **Alternatives:** (1) Fold the check into the LLM prompt — unsafe and non-reproducible. (2) Trust the upload identity guess only — misses full-workbook evidence. (3) Block all non-verified accounts automatically — too strict until PDF/image OCR verification has an equivalent deterministic policy.
- **Consequences:** Analysts can verify known accounts against workbook evidence before normalization, and audit logs can retain the verification summary. Current deterministic scanning is Excel-only; PDF/image support remains future work.

### DEC-027: Analyst-selected subject account is review-gated mapping context
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** Investigators often know the requested subject account before BSIE can fully interpret an unfamiliar workbook. That account can help mapping assist understand statement perspective, but it must not silently override evidence when upload inference points to a different account.
- **Decision:** Expose known subject account/name in Step 2, block mapping confirmation when the selected account conflicts with statement-inferred account until the analyst confirms the override, and pass `subject_context` to mapping assist, vision assist, and mapping confirmation audit logs. The selected account remains analyst authority; LLM output may warn about conflicts but may not change account values.
- **Alternatives:** (1) Keep account collection only in Step 3 — too late to help mapping and conflict review. (2) Always trust inferred account — can ignore legal-request context. (3) Let LLM infer/replace the subject account — unsafe for evidence integrity.
- **Consequences:** Account conflicts become explicit review events before normalization. Mapping assist can use subject perspective without inventing accounts. Full workbook account-presence verification is still future work beyond the current identity/sample-row context.

### DEC-026: Analyst-selected bank is authoritative after explicit review
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** Investigators may know the issuing bank from the legal request even when BSIE's auto-detection says a different bank because the file layout resembles another template. Auto-detection should help, but it must not override known investigator context or silently learn under the wrong bank.
- **Decision:** Treat the selected bank as the authority for the current mapping run after explicit analyst confirmation. If selected bank differs from detected bank, Step 2 blocks until the analyst confirms the bank override; mapping assist is prompted to map under the selected bank; mapping confirmation records `bank_authority` and bank feedback in audit context.
- **Alternatives:** (1) Always trust auto-detection — can attach mappings to the wrong bank. (2) Always trust user selection without a gate — hides conflicts and weakens auditability. (3) Disable mapping assist on bank conflicts — safer but less useful for unfamiliar layouts where help is most needed.
- **Consequences:** Auto-detection remains advisory. Overrides are visible, analyst-confirmed, and traceable. Template variants created from promoted mappings are tied to the selected bank, not the detected-but-overridden bank.

### DEC-025: Balance-like mapping suggestions prefer curated statement-balance aliases
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** Some statements expose multiple balance-like headers, and LLM/profile suggestions may choose a lower-priority alias such as `ยอดหลังรายการ` even when the bank/config-curated statement balance column `ยอดคงเหลือ` is also present. This left the TTB benchmark with one avoidable miss despite valid mapping semantics.
- **Decision:** Repair suggested mappings before analyst confirmation so `balance` prefers curated aliases (`ยอดคงเหลือ`, `Outstanding Balance`, `Ledger Balance`, etc.) over lower-priority after-transaction synonyms when both are available. Keep lower-priority aliases usable when no stronger alias exists.
- **Alternatives:** (1) Let the LLM decide every time — keeps ambiguity and benchmark variance. (2) Reject lower-priority balance aliases in validation — too strict because some statements only expose those headers. (3) Change benchmark expectation only — hides the ambiguity instead of improving suggestions.
- **Consequences:** Auto/profile/variant/LLM suggestions become more stable without mutating confirmed mappings. Future balance aliases should be added to the preference list with care because the ordering is now a deterministic contract.

### DEC-024: Direction-marker amount layouts are first-class mapping paths
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** BAY-like statements can represent transaction direction as one unsigned amount column plus a separate marker column (`DR`/`CR`, `IN`/`OUT`, or Thai deposit/withdraw markers). Treating that marker as debit/credit made otherwise correct mappings fail validation and could hide the true statement layout.
- **Decision:** Add `amount + direction_marker` as a distinct validated amount path. Mapping assist may suggest `direction_marker`, preview signs unsigned amounts from the marker, the normalizer supports the same marker mode, and BAY's built-in config now declares `format_type`/`amount_mode` as `direction_marker`.
- **Alternatives:** (1) Keep forcing marker columns into `debit`/`credit` — validates poorly and misrepresents the source layout. (2) Treat all such amounts as signed amounts — loses direction when the amount column is unsigned. (3) Handle BAY as a one-off special case — duplicates logic and makes future marker layouts harder to audit.
- **Consequences:** Direction-marker mappings can pass validation and dry-run preview without debit/credit columns. Regression tests now cover validator, assist repair, and normalizer behavior. Future marker aliases should be added to the shared marker sets before relying on them in configs.

### DEC-023: Mapping model benchmarks must cover all supported bank keys before policy changes
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** The first task-specific fixture benchmark covered only three layouts. Expanding the same harness to all eight supported bank keys revealed a much larger gap between `gemma4:26b` and smaller Gemma variants, especially on noisy, mixed-header, direction-marker, and account-format edge cases.
- **Decision:** Treat all-supported-bank synthetic fixture coverage as the minimum benchmark bar before changing mapping-assist model defaults or any future automation policy. Keep `gemma4:26b` as the mapping-assist default based on the expanded 8-bank result.
- **Alternatives:** (1) Use only smoke/JSON benchmarks — too weak for mapping accuracy. (2) Benchmark only the banks currently being tested manually — faster but misses regressions in less common bank formats. (3) Use real case statements — not acceptable for a reusable benchmark.
- **Consequences:** Future fixture work should add more layouts per bank, but every benchmark comparison should continue reporting all supported bank keys and edge-case coverage.

### DEC-022: Mapping model selection uses a reproducible synthetic fixture harness
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** Manual ad hoc benchmark snippets were useful for exploration, but model-selection decisions for evidence-sensitive mapping should be reproducible and should not depend on real case data or one-off shell history.
- **Decision:** Add `scripts/benchmark_mapping_models.py` as the reusable local-only harness for synthetic mapping fixtures. It runs text and/or vision mapping assist against fixed synthetic fixtures, scores expected mapping fields, and writes JSON/Markdown artifacts under ignored `artifacts/llm_mapping_benchmarks/`.
- **Alternatives:** (1) Keep manual snippets in docs — quick but hard to rerun safely. (2) Use real uploaded statements for accuracy tests — more realistic but not acceptable for a reusable benchmark log. (3) Fold task benchmarks into normal pytest — would make tests require Ollama and local models.
- **Consequences:** Future model changes can be compared with the same synthetic fixtures and output format. The harness is not a CI test because it depends on local Ollama model availability.

### DEC-021: Mapping assist defaults to Gemma 4 26B with bounded no-think structured calls
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** Smoke tests showed several Gemma variants can return valid JSON, but task-specific synthetic mapping fixtures showed a larger accuracy gap. `gemma4:26b` scored 100% on text and vision mapping fixtures, while `gemma4:e4b` missed the noisy OCR-like fixture and `gemma4:e2b` was too lossy. The previous mapping-assist production path also did not explicitly disable thinking or cap structured output tokens.
- **Decision:** Mapping assist now defaults to `gemma4:26b` when `OLLAMA_MAPPING_MODEL` is not set, and both text and vision mapping assist calls pass `think=false` with a bounded token budget. Keep `gemma4:e4b` as the fast fallback role rather than the primary mapping model.
- **Alternatives:** (1) Keep `qwen2.5:14b` as the implicit mapping default — currently not installed on this machine and would fail by default. (2) Promote `gemma4:e4b` because it is faster — good smoke result but weaker on noisy OCR-like mapping. (3) Use `gemma4:e2b` for speed — too lossy for evidence-sensitive mapping assistance.
- **Consequences:** Default local mapping assist is usable on the current machine without extra env configuration, but it has higher cold-load cost. Suggestions remain validation-gated, column-constrained, and analyst-applied only.

### DEC-020: Gemma 4 variants need task-specific accuracy tests before default changes
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** After installing `gemma4:e2b` and `gemma4:26b`, a Gemma-only benchmark showed all tested Gemma variants pass strict JSON text and vision smoke tests. `e2b` is fastest overall, `e4b` remains a balanced pinned model, and `26b` has heavier cold load but similar warm latency on the tiny smoke prompt.
- **Decision:** Keep `gemma4:e4b` as the balanced pinned fast fallback for now. Treat `gemma4:e2b` as an ultra-fast/lightweight candidate and `gemma4:26b` as the next quality candidate for synthetic mapping/OCR fixtures. Do not switch defaults based on smoke latency alone.
- **Alternatives:** (1) Promote `gemma4:e2b` because it is fastest — risks lower mapping/OCR quality. (2) Promote `gemma4:26b` because official benchmarks are stronger — risks heavier cold load and memory pressure. (3) Use `gemma4:latest` because it is currently fast/warm — not reproducible.
- **Consequences:** The next model-selection step should benchmark synthetic bank-header mapping and document-layout tasks, not just JSON compliance. Role defaults remain stable until those task-specific results are available.

### DEC-019: Benchmark thinking models through Ollama native chat when disabling reasoning
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** Installed Qwen/Gemma tags advertise `thinking` capability. Under the BSIE system prompt, the OpenAI-compatible `/v1/chat/completions` path produced empty `message.content` for Qwen models when capped, because output budget was spent on reasoning before the final answer. Ollama's documented `think` control is reliable through native `/api/chat`.
- **Decision:** When BSIE explicitly sets `think=false` for local benchmarking, route calls through native Ollama `/api/chat` and map native token counters back to the existing service response shape. For currently installed models, use the sweep results as operational guidance: `gemma4:e4b` is the strongest installed fast/vision candidate, `qwen3.5:9b` is the best installed Qwen text candidate, and Qwen 27B tags should not be defaults for interactive mapping due to latency.
- **Alternatives:** (1) Keep benchmarking through `/v1/chat/completions` — reproducible with existing code but mismeasures thinking models and can report false JSON failures. (2) Raise output limits until reasoning finishes — works but turns a smoke benchmark into a slow reasoning benchmark. (3) Disable thinking only through prompt text — not reliable for the installed Qwen tags.
- **Consequences:** Benchmark results are more representative for low-latency mapping assist. Production chat behavior remains unchanged unless `think` is passed explicitly. Future model decisions should test native `think=false` and any intended production endpoint path separately.

### DEC-018: Benchmark results do not change the configured baseline roles yet
- **Date:** 2026-04-24
- **Status:** superseded by DEC-035
- **Context:** The first live benchmark found installed `qwen3.6:27b` and `gemma4:e4b`, while the documented baseline text/vision models from DEC-008 were not installed. `qwen3.6:27b` produced valid JSON but was too slow for interactive mapping UX.
- **Decision:** Keep the existing role defaults unchanged for now. Record the local benchmark in `docs/LOCAL_LLM_BENCHMARKS.md`, but do not switch text defaults to `qwen3.6:27b` or use `gemma4:e4b` as the primary mapping model based on a single run.
- **Alternatives:** (1) Change text default to `qwen3.6:27b` because it is installed — works but is too slow. (2) Change text default to `gemma4:e4b` because it is faster — weaker for Thai/JSON/mapping reasoning and showed variable JSON compliance. (3) Block Phase 4 until baseline models are installed — unnecessary because Phase 4 can preserve role-based config.
- **Consequences:** Superseded by DEC-035; do not install/pull the Qwen 2.5 models just to satisfy this historical benchmark plan.

### DEC-017: OCR/vision mapping assist reads evidence by file_id and remains suggestion-only
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** PDF/image statements can produce weak OCR headers where text-only mapping assist has limited context. Vision assistance can help interpret the original document preview, but it must not bypass analyst review or accept arbitrary file paths.
- **Decision:** Add `/api/mapping/assist/vision`, backed by `suggest_mapping_with_vision_llm(...)`. The endpoint accepts `file_id`, resolves the stored evidence file, rejects paths outside `EVIDENCE_DIR`, sends only the first PDF page or image bytes to the local vision model, constrains output to existing OCR/extracted columns, validates the merged mapping, and returns `suggestion_only=true` / `auto_pass_eligible=false`.
- **Alternatives:** (1) Upload a second copy of the file from the browser — simpler UI but duplicates evidence handling. (2) Let the vision model create new columns/rows — tempting for OCR repair but unsafe because it can invent evidence. (3) Run automatically during upload — adds latency and weakens explicit analyst control.
- **Consequences:** Analysts can request visual help for PDF/image mapping while preserving evidence lineage, path confinement, validation, and explicit apply/confirm gates. OCR repair and row extraction remain future work.

### DEC-016: Local LLM benchmark uses synthetic prompts only
- **Date:** 2026-04-24
- **Status:** accepted
- **Context:** Phase 3 needs model benchmarking for text/fast/vision roles, but benchmark tooling must not leak, persist, or transform investigative evidence. It should also be usable before Ollama is fully configured by failing closed with structured status.
- **Decision:** Add `/api/llm/benchmark` backed by `benchmark_llm_roles(...)`. It sends only a fixed synthetic JSON prompt, disables database auto-context, does not persist results, supports `text`, `fast`, and optional `vision` roles, records latency/token/JSON-validity metrics, and returns `offline`/`partial` instead of throwing for unavailable local Ollama calls.
- **Alternatives:** (1) Benchmark with real uploaded statements — more realistic but unsafe for evidence handling. (2) Keep benchmarking as an ad hoc shell/manual process — lower code cost but hard to reproduce or expose in UI later.
- **Consequences:** Operators can compare local models without involving case data. Real machine benchmarks still require local Ollama and the configured models to be installed.

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
- **Status:** superseded by DEC-035
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
