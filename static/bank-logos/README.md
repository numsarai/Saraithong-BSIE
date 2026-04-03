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
- Use [`/Users/saraithong/Documents/bsie/scripts/sync_bank_logos.py`](/Users/saraithong/Documents/bsie/scripts/sync_bank_logos.py)
  to refresh the current real-logo set from each bank's official domain favicon/app icon.
- Current fetched asset provenance is tracked in
  [`/Users/saraithong/Documents/bsie/static/bank-logos/sources.json`](/Users/saraithong/Documents/bsie/static/bank-logos/sources.json).
- These files are third-party bank trademarks. Treat them as product branding assets,
  not evidence, and replace them with exact brand artwork later if the bank provides a
  better official press-kit/logo file.
