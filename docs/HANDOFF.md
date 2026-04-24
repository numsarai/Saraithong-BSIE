# Handoff Log

> อัพเดตทุกครั้งก่อนสลับ agent หรือจบ session
> Agent ตัวถัดไปจะอ่านไฟล์นี้เป็นอย่างแรก

## Current State

- **Last agent:** Codex (GPT-5)
- **Date:** 2026-04-24
- **Branch:** `Smarter-BSIE`
- **Runtime mode:** local-only อีกครั้ง
- **Baseline:** backend `344 passed`, frontend `37 passed`, frontend build passed
- **Auth/DB:** local JWT auth + local SQLite WAL (`bsie.db`)
- **Cloud status:** repo ไม่ผูกกับ Vercel, Fly.io, หรือ Supabase แล้วใน working tree ปัจจุบัน

## Done (latest session) — Mapping Assist Fixture Benchmark

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
