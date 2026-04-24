# Local LLM Benchmarks

> Local-only benchmark log. Prompts are synthetic and do not include case evidence.

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
