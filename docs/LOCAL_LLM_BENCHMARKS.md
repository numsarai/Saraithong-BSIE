# Local LLM Benchmarks

> Local-only benchmark log. Prompts are synthetic and do not include case evidence.

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
