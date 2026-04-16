# Config Registry

> Updated for BSIE v4.1

This registry is the built-in validation layer for BSIE bank formats.

**Supported banks (10 configs):** BBL, BAY, KBANK, KTB, SCB, TTB, GSB, CIAF, generic, OFX.

Each entry ties together:
- a built-in bank config in [`/Users/saraithong/Documents/bsie/config`](/Users/saraithong/Documents/bsie/config)
- a golden sample file already stored in the repo
- the expected bank auto-detection result
- optional normalization assertions for critical standard-schema fields

## How To Add A New Bank Or Subformat

1. Add or update the built-in config in [`/Users/saraithong/Documents/bsie/config`](/Users/saraithong/Documents/bsie/config).
2. Add at least one anonymized sample file to the repo.
3. Add a registry entry in [`/Users/saraithong/Documents/bsie/config_registry/registry.json`](/Users/saraithong/Documents/bsie/config_registry/registry.json).
4. Include:
   - `config_key`
   - `sample_path`
   - `expected_bank`
   - `normalize_assert` when the format should also pass normalization checks
5. Run:

```bash
python scripts/validate_config_registry.py
pytest -q
```

## Validation Rules

- The config file must exist under the built-in config directory.
- The config must include explicit `detection.keywords` and `detection.strong_headers`.
- Some configs (e.g., GSB) also use `detection.body_keywords` for content-based bank detection when header keywords are insufficient.
- The sample file must exist.
- Auto-detection must match `expected_bank`.
- If `normalize_assert` is present, normalization must produce rows and include the required standard-schema columns.

## Important Boundary

This registry validates explicit built-in configs only.

Runtime-learned bank fingerprints and mapping memory remain useful for analyst workflows, but they do not replace built-in config ownership, review, or regression coverage.
