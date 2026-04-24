# Local LLM Benchmarks

> Local-only benchmark log. Prompts are synthetic and do not include case evidence.

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
