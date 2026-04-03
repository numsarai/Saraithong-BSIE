Bank logo override slot
=======================

Drop official bank assets here using the bank key as the filename:

- `scb.svg`
- `kbank.svg`
- `baac.png`

Rules:

- UI prefers these static assets automatically when a matching file exists.
- Workbook exports can embed raster overrides (`.png`, `.jpg`, `.jpeg`) directly.
- If only an SVG override exists, UI will use it and workbook exports will fall back
  to the deterministic generated badge until a raster override is added.
- When no override exists, BSIE uses the generated badge from
  [`/Users/saraithong/Documents/bsie/core/bank_logo_registry.py`](/Users/saraithong/Documents/bsie/core/bank_logo_registry.py).
