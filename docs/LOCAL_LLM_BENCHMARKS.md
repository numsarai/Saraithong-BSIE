# Local LLM Benchmarks

> Local-only benchmark log. Prompts are synthetic and do not include case evidence.

## 2026-04-24 — Balance Alias Disambiguation Follow-up

### Environment

- Branch: `Smarter-BSIE`
- Runtime: local Ollama via `OLLAMA_BASE_URL=http://localhost:11434`
- Benchmark source: `scripts/benchmark_mapping_models.py`
- Endpoint path: native Ollama `/api/chat` through `think=false`
- Evidence data: none; all fixtures are synthetic

This follow-up added deterministic suggestion repair for ambiguous balance-like columns. When a suggested mapping points `balance` to a lower-priority alias such as `ยอดหลังรายการ` while a curated statement-balance alias such as `ยอดคงเหลือ` is present, BSIE repairs the suggestion before validation and analyst review.

Targeted TTB command:

```bash
.venv/bin/python scripts/benchmark_mapping_models.py --models gemma4:26b --fixture ttb_ambiguous_amount_balance --mode both --run-id balance-ttb-gemma26b-20260424120508
```

Targeted result:

| Model | Fixture | Text score | Text validation | Vision score | Vision validation |
|---|---|---:|---|---:|---|
| `gemma4:26b` | `ttb_ambiguous_amount_balance` | 6 / 6 = 100.00% | `True` | 6 / 6 = 100.00% | `True` |

8-bank re-run command:

```bash
.venv/bin/python scripts/benchmark_mapping_models.py --models gemma4:26b --mode both --run-id balance-8bank-gemma26b-20260424120540
```

8-bank re-run result:

| Model | Text score | Text avg | Vision score | Vision avg | Notes |
|---|---:|---:|---:|---:|---|
| `gemma4:26b` | 55 / 55 = 100.00% | 6,148.77 ms | 55 / 55 = 100.00% | 6,805.12 ms | Validation passed for every fixture; no misses in the current synthetic set |

### Takeaways

- The previous TTB balance miss is now handled deterministically before analyst review.
- The current 8-bank synthetic benchmark has no remaining `gemma4:26b` misses, but it is still synthetic and should not justify auto-apply behavior.
- Next benchmark work should add more fixtures per bank and real-world layout variants without using case evidence.

## 2026-04-24 — Direction-Marker Mapping Follow-up

### Environment

- Branch: `Smarter-BSIE`
- Runtime: local Ollama via `OLLAMA_BASE_URL=http://localhost:11434`
- Benchmark source: `scripts/benchmark_mapping_models.py`
- Endpoint path: native Ollama `/api/chat` through `think=false`
- Evidence data: none; all fixtures are synthetic

This follow-up made `direction_marker` a first-class mapping path for layouts with one unsigned amount column plus a separate direction marker such as `DR`/`CR`, `IN`/`OUT`, or Thai deposit/withdraw markers.

Targeted BAY command:

```bash
.venv/bin/python scripts/benchmark_mapping_models.py --models gemma4:26b --fixture bay_direction_marker_amount --mode both --run-id direction-marker-bay-20260424115658
```

Targeted result:

| Model | Fixture | Text score | Text validation | Vision score | Vision validation |
|---|---|---:|---|---:|---|
| `gemma4:26b` | `bay_direction_marker_amount` | 8 / 8 = 100.00% | `True` | 8 / 8 = 100.00% | `True` |

8-bank re-run command:

```bash
.venv/bin/python scripts/benchmark_mapping_models.py --models gemma4:26b --mode both --run-id direction-marker-8bank-gemma26b-20260424115736
```

8-bank re-run result:

| Model | Text score | Text avg | Vision score | Vision avg | Notes |
|---|---:|---:|---:|---:|---|
| `gemma4:26b` | 54 / 55 = 98.18% | 6,216.47 ms | 54 / 55 = 98.18% | 6,728.69 ms | Validation passed for every fixture; only miss remains the intentionally ambiguous TTB balance choice |

### Takeaways

- `bay_direction_marker_amount` now validates cleanly without forcing the marker column into debit/credit.
- The expected field total increased from 54 to 55 because the BAY fixture now explicitly scores `direction_marker`.
- `gemma4:26b` remains the mapping-assist default recommendation; the deterministic backend fix removed the BAY validation blocker.

## 2026-04-24 — Expanded 8-Bank Mapping Fixture Benchmark

### Environment

- Branch: `Smarter-BSIE`
- Runtime: local Ollama via `OLLAMA_BASE_URL=http://localhost:11434`
- Benchmark source: `scripts/benchmark_mapping_models.py`
- Endpoint path: native Ollama `/api/chat` through `think=false`
- Evidence data: none; all fixtures are synthetic

The reusable harness now includes one or more fixtures for every supported BSIE bank key: `scb`, `kbank`, `bbl`, `ktb`, `bay`, `ttb`, `gsb`, and `baac`.

Expanded fixture set:

| Fixture | Bank | Edge case |
|---|---|---|
| `thai_debit_credit` | `scb` | Thai debit/credit columns |
| `english_signed_amount` | `kbank` | English signed amount columns |
| `ocr_noisy_signed_amount` | `ktb` | Thai OCR-like abbreviated headers |
| `bbl_leading_zero_counterparty` | `bbl` | Counterparty accounts with leading zeros |
| `bay_direction_marker_amount` | `bay` | Unsigned amount plus direction marker |
| `ttb_ambiguous_amount_balance` | `ttb` | Ambiguous balance columns |
| `gsb_mymo_mixed_headers` | `gsb` | MyMo-style uppercase mixed headers |
| `baac_scientific_counterparty` | `baac` | Counterparty account rendered as scientific notation |

Command:

```bash
.venv/bin/python scripts/benchmark_mapping_models.py --run-id 20260424-expanded-8bank-gemma-comparison
```

### Results

| Model | Text score | Text avg | Vision score | Vision avg | Notes |
|---|---:|---:|---:|---:|---|
| `gemma4:26b` | 53 / 54 = 98.15% | 5,749.02 ms | 53 / 54 = 98.15% | 6,790.99 ms | Best by a wide margin; missed only the intentionally ambiguous TTB balance choice |
| `gemma4:e4b` | 18 / 54 = 33.33% | 7,658.07 ms | 21 / 54 = 38.89% | 7,181.56 ms | Handles clean fixtures, weak on noisy/mixed/edge-case layouts |
| `gemma4:e2b` | 20 / 54 = 37.04% | 3,553.45 ms | 4 / 54 = 7.41% | 4,573.94 ms | Fast but too lossy for mapping assist |

Additional validation notes:

- At the time of this run, `bay_direction_marker_amount` scored correct on expected fields for `gemma4:26b`, but validation was `false` because direction-marker amount layouts were not yet first-class. This was fixed in the direction-marker follow-up above.
- `ttb_ambiguous_amount_balance` exposed the intended ambiguity: `gemma4:26b` selected `ยอดหลังรายการ` while the fixture expected `ยอดคงเหลือ`.

### Takeaways

- The expanded fixture set strengthens the decision to keep `gemma4:26b` as mapping-assist default.
- The next deterministic backend improvement should consider direction-marker amount layouts so BAY-like exports can validate without forcing debit/credit columns.
- Keep `gemma4:e4b` and `gemma4:e2b` out of primary mapping assist unless a future prompt or model update improves edge-case recall.

## 2026-04-24 — Mapping Assist Fixture Benchmark

### Environment

- Branch: `Smarter-BSIE`
- Runtime: local Ollama via `OLLAMA_BASE_URL=http://localhost:11434`
- Benchmark source: `services.mapping_assist_service.suggest_mapping_with_llm(...)` and `suggest_mapping_with_vision_llm(...)`
- Endpoint path: native Ollama `/api/chat` through `think=false`
- Evidence data: none; all fixtures are synthetic bank-header / OCR-layout examples

Reproducible harness added:

```bash
.venv/bin/python scripts/benchmark_mapping_models.py --run-id 20260424-gemma-mapping-fixtures
```

The harness writes ignored artifacts under `artifacts/llm_mapping_benchmarks/`:

- `mapping_model_benchmark_<run-id>.json`
- `mapping_model_benchmark_<run-id>.md`

Before this run, production mapping assist was adjusted to use `think=false` and a bounded output budget for structured JSON calls. A quick pre-fix probe showed the old path could be slow and incomplete under Gemma: `gemma4:e2b` took about 14.1s and returned only `date`/`description` for a Thai debit/credit fixture, while `gemma4:e4b` and `gemma4:26b` took about 24.7s and 32.9s for the same shape.

### Fixtures

| Fixture | Shape | Expected fields |
|---|---|---|
| `thai_debit_credit` | Thai debit/credit statement columns | date, time, description, debit, credit, balance, channel, counterparty_account |
| `english_signed_amount` | English signed amount columns | date, time, description, amount, balance, channel, counterparty_account |
| `ocr_noisy_signed_amount` | Thai OCR-like abbreviated columns with signed amount | date, description, amount, balance, channel, counterparty_account |

### Results

| Model | Text score | Text avg | Vision score | Vision avg | Notes |
|---|---:|---:|---:|---:|---|
| `gemma4:e2b` | 14 / 21 = 66.67% | 4,022.08 ms | 3 / 21 = 14.29% | 4,264.31 ms | Fast but unreliable for noisy mapping; vision often selected row values instead of column names, which BSIE safely filtered |
| `gemma4:e4b` | 15 / 21 = 71.43% | 7,375.73 ms | 15 / 21 = 71.43% | 7,043.96 ms | Strong on clean fixtures, failed noisy OCR-like Thai fixture |
| `gemma4:26b` | 21 / 21 = 100% | 8,520.42 ms | 21 / 21 = 100% | 6,688.96 ms | Best accuracy; passed clean, English signed amount, and noisy Thai OCR-like fixtures |

Re-run from the committed harness (`20260424-gemma-mapping-fixtures`) produced the same ranking:

| Model | Text score | Text avg | Vision score | Vision avg |
|---|---:|---:|---:|---:|
| `gemma4:26b` | 21 / 21 = 100% | 5,759.21 ms | 21 / 21 = 100% | 6,204.92 ms |
| `gemma4:e4b` | 15 / 21 = 71.43% | 7,310.27 ms | 15 / 21 = 71.43% | 6,454.89 ms |
| `gemma4:e2b` | 13 / 21 = 61.90% | 4,967.51 ms | 3 / 21 = 14.29% | 4,664.24 ms |

### Follow-up Prompt Experiment

An extra prompt constraint was tested to say every mapping value must be copied exactly from the column list and never from sample rows. It made `gemma4:e2b` and `gemma4:e4b` more conservative and reduced recall, so that prompt change was reverted. The service still keeps the safer structural controls: LLM output is cleaned against known columns, validation must pass, and the suggestion remains analyst-applied only.

### Takeaways

- Use `gemma4:26b` as the default mapping-assist model on this machine when `OLLAMA_MAPPING_MODEL` is not set.
- Keep `gemma4:e4b` as the fast fallback / lightweight model, not the primary mapping assistant.
- Treat `gemma4:e2b` as a triage candidate only; it is too lossy for evidence-sensitive mapping suggestions.
- Vision mapping assist is viable with `gemma4:26b`, but should still remain suggestion-only and validation-gated.
- This benchmark is still synthetic. Before any auto-apply behavior, expand fixtures with more Thai bank layouts, OCR noise, merged cells, balance anomalies, and ambiguous amount modes.

## 2026-04-24 — Gemma Variant Follow-up Sweep

### Environment

- Branch: `Smarter-BSIE`
- Runtime: local Ollama via `OLLAMA_BASE_URL=http://localhost:11434`
- Benchmark source: `services.llm_service.benchmark_llm_roles(...)`
- Endpoint path: native Ollama `/api/chat` with `think=false`
- Evidence data: none; benchmark prompt and 1x1 PNG are synthetic

Newly installed local models at run time:

| Model | ID | Size | Note |
|---|---|---:|---|
| `gemma4:e2b` | `7fbdbf8f5e45` | 7.2 GB | Newly installed edge model |
| `gemma4:26b` | `5571076f3d70` | 17 GB | Newly installed MoE workstation model |

### Single-Pass Gemma Sweep

| Model | Text status | Text duration | Vision status | Vision duration | Notes |
|---|---|---:|---|---:|---|
| `gemma4:e2b` | `ok` | 4,389.15 ms | `ok` | 757.84 ms | Cold text load visible; vision already warm |
| `gemma4:e4b` | `ok` | 6,120.88 ms | `ok` | 1,378.78 ms | Same pinned baseline; cold-ish after model switch |
| `gemma4:latest` | `ok` | 577.38 ms | `ok` | 994.74 ms | Same local ID as `e4b`, warmed by prior `e4b` call |
| `gemma4:26b` | `ok` | 8,468.53 ms | `ok` | 1,858.47 ms | Largest cold load; JSON and vision smoke both passed |

Because `gemma4:e4b` and `gemma4:latest` share the same local ID, their single-pass latency mainly shows warm/cold load effects, not a real quality difference.

### Three-Iteration Focused Sweep

| Model | Text avg | Text warm runs | Vision avg | Vision warm runs | Result |
|---|---:|---|---:|---|---|
| `gemma4:e2b` | 1,682.78 ms | 376.02 ms, 368.96 ms | 492.80 ms | 369.59 ms, 374.22 ms | Fastest cold+warm overall |
| `gemma4:e4b` | 2,251.77 ms | 492.44 ms, 483.00 ms | 646.14 ms | 481.54 ms, 468.16 ms | Balanced pinned default candidate |
| `gemma4:26b` | 3,045.11 ms | 489.03 ms, 471.78 ms | 890.70 ms | 487.21 ms, 484.61 ms | Higher-quality candidate; cold load heavier |

All three variants returned valid JSON on all text and vision runs.

### Takeaways

- `gemma4:e2b` is the fastest Gemma option in this smoke test and is a good candidate for ultra-fast fallback / lightweight document triage.
- Keep `gemma4:e4b` as the balanced pinned fast fallback for now; it is stronger than `e2b` and still warm-runs under ~0.5s on this prompt.
- `gemma4:26b` is worth testing on real mapping/OCR-like synthetic fixtures next. The cold load is heavier, but warm latency was close to `e4b` on this tiny JSON prompt.
- Do not switch production-like defaults to `gemma4:latest`; even when it currently points to the same ID as `e4b`, the tag is not reproducible enough.
- This benchmark only measures strict JSON smoke behavior, not mapping accuracy or OCR quality. The next useful test should use synthetic bank-header and document-layout fixtures.

## 2026-04-24 — Installed Model Sweep

### Environment

- Branch: `Smarter-BSIE`
- Runtime: local Ollama via `OLLAMA_BASE_URL=http://localhost:11434`
- Benchmark source: `services.llm_service.benchmark_llm_roles(...)`
- Iterations: `1`
- Endpoint path: native Ollama `/api/chat` when `think=false` is set
- Evidence data: none; benchmark prompt and 1x1 PNG are synthetic

During setup, the OpenAI-compatible `/v1/chat/completions` path returned empty `message.content` for Qwen thinking models under the BSIE system prompt because reasoning consumed the capped output budget first. Ollama's documented `think` control applies to native chat/generate requests, so benchmark calls now use native `/api/chat` whenever `think` is explicitly set.

Installed local models at run time:

| Model | ID | Size | Note |
|---|---|---:|---|
| `qwen3.5:9b` | `6488c96fa5fa` | 6.6 GB | Installed during this session |
| `qwen3.6:27b` | `a50eda8ed977` | 17 GB | Large reasoning/vision-capable tag |
| `qwen3.5:27b` | `7653528ba5cb` | 17 GB | Large reasoning/vision-capable tag |
| `gemma4:latest` | `c6eb396dbd59` | 9.6 GB | Same local ID as `gemma4:e4b` |
| `gemma4:e4b` | `c6eb396dbd59` | 9.6 GB | Preferred pinned Gemma tag |

### Sweep Results

| Model | Text status | Text duration | Text tokens | Vision status | Vision duration | Vision tokens | Notes |
|---|---|---:|---:|---|---:|---:|---|
| `qwen3.5:9b` | `ok` | 2,558.23 ms | 1,319 / 18 | `error` | 131.14 ms | 0 / 0 | Fastest Qwen text result; vision runner 500 |
| `qwen3.6:27b` | `ok` | 30,704.65 ms | 1,319 / 18 | `error` | 268.73 ms | 0 / 0 | Functional text but too slow for interactive mapping |
| `qwen3.5:27b` | `ok` | 19,708.81 ms | 1,319 / 18 | `error` | 200.22 ms | 0 / 0 | Faster than `qwen3.6:27b`, still high latency |
| `gemma4:latest` | `ok` | 6,050.71 ms | 1,042 / 19 | `ok` | 1,316.14 ms | 1,297 / 18 | Same model ID as pinned tag; text localized field names |
| `gemma4:e4b` | `ok` | 579.06 ms | 1,042 / 19 | `ok` | 993.94 ms | 1,297 / 18 | Best installed fast + vision smoke result |

### Takeaways

- For currently installed models, prefer `gemma4:e4b` as the fast fallback and provisional vision smoke model.
- Prefer `qwen3.5:9b` over the 27B Qwen tags for interactive text experiments when Qwen-family reasoning is needed.
- Keep strict schema validation around `gemma4:e4b`; it returned valid JSON but localized the `fields` values in the text smoke response.
- Do not use the installed Qwen tags for vision on this machine yet; every Qwen vision smoke failed with Ollama runner `500`.
- Avoid `qwen3.6:27b` as a default interactive mapping model; valid JSON took about 30.7 seconds even with `think=false`.
- Keep avoiding `:latest` in production-like flows; `gemma4:latest` and `gemma4:e4b` currently share an ID, but the pinned tag is more reproducible.
- The earlier `qwen2.5:14b` / `qwen2.5vl:7b` baseline remains unverified because those models are not installed.

## 2026-04-24 — Initial Local Ollama Run

### Environment

- Branch: `Smarter-BSIE`
- Runtime: local Ollama via `OLLAMA_BASE_URL=http://localhost:11434`
- Benchmark source: `services.llm_service.benchmark_llm_roles(...)`
- Iterations: `1`
- Evidence data: none; benchmark prompt is synthetic

Installed local models at run time:

| Model | Size | Note |
|---|---:|---|
| `qwen3.6:27b` | 17 GB | Installed, not current default role |
| `qwen3.5:27b` | 17 GB | Installed, not benchmarked |
| `gemma4:latest` | 9.6 GB | Same local ID as `gemma4:e4b` |
| `gemma4:e4b` | 9.6 GB | Installed fast fallback |

Configured role defaults at run time:

| Role | Configured model | Result |
|---|---|---|
| `text` | `qwen2.5:14b` | Not installed, Ollama 404 |
| `fast` | `gemma4:e4b` | Installed |
| `vision` | `qwen2.5vl:7b` | Not installed, Ollama 404 |

### Default Role Run

Command shape:

```bash
.venv/bin/python - <<'PY'
import asyncio, json
from services.llm_service import benchmark_llm_roles

async def main():
    result = await benchmark_llm_roles(iterations=1, include_vision=True)
    print(json.dumps(result, ensure_ascii=False, indent=2))

asyncio.run(main())
PY
```

Result summary:

| Role | Model | Status | Duration | Notes |
|---|---|---|---:|---|
| `text` | `qwen2.5:14b` | `error` | 113.12 ms | Model not installed |
| `fast` | `gemma4:e4b` | `invalid_json` | 40,880.92 ms | Model responded but did not satisfy strict JSON check in this run |
| `vision` | `qwen2.5vl:7b` | `error` | 83.54 ms | Model not installed |

Overall status: `partial`.

### Installed-Model Override Run

Command shape:

```bash
.venv/bin/python - <<'PY'
import asyncio, json
from services.llm_service import benchmark_llm_roles

async def main():
    result = await benchmark_llm_roles(
        roles=["text", "fast"],
        iterations=1,
        model_overrides={"text": "qwen3.6:27b", "fast": "gemma4:e4b"},
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))

asyncio.run(main())
PY
```

Result summary:

| Role | Model | Status | Duration | Prompt tokens | Completion tokens | Notes |
|---|---|---|---:|---:|---:|---|
| `text` | `qwen3.6:27b` | `ok` | 105,522.48 ms | 1,295 | 908 | JSON valid, too slow for default mapping UX |
| `fast` | `gemma4:e4b` | `ok` | 14,392.83 ms | 1,022 | 502 | JSON valid in override run |

Overall status: `ok`.

### Takeaways

- Do not change defaults based on this run; the intended baseline models from `DEC-008` are not installed yet.
- `qwen3.6:27b` is functional but too slow for interactive mapping assist on this machine.
- `gemma4:e4b` is available and much faster, but JSON compliance varied across runs.
- Next live benchmark should install/pull `qwen2.5:14b` and `qwen2.5vl:7b`, then rerun text/fast/vision roles.
