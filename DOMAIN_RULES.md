# BSIE Domain Rules

> Updated for BSIE v4.0

## Evidence Integrity

- Raw source values must never be discarded.
- Manual edits must be auditable.
- Duplicate records are flagged, not deleted.
- Inferred matches are suggestions until confirmed.

## Account Rules

- Normalized account numbers must be digits only.
- Valid normalized account numbers must be exactly 10 or 12 digits.
- Preserve the raw account value separately from the normalized account value.
- Treat leading-zero loss as a forensic issue, not a harmless cleanup detail.
- Treat scientific notation from Excel as suspicious input that must be normalized carefully and remain traceable to the original raw cell value.
- If Excel has already rendered an account number as `1.2345E+09`, preserve that raw representation somewhere traceable even if a normalized digits-only value is later derived.
- If normalization is uncertain, mark for review instead of guessing.
- Never silently pad, trim, or coerce a malformed account number into a valid-looking value without preserving the source form.

## Intake Rules

- Keep original uploaded files as evidence.
- Keep the file hash and duplicate-upload history.
- Preserve workbook context such as sheet name, header row, and raw row payload when available.
- If a bank format is ambiguous, prefer explicit analyst confirmation over silent auto-selection.
- Supported formats: Excel (.xlsx, .xls), OFX, PDF, and image (via OCR).
- Supported banks: BBL, BAY, KBANK, KTB, SCB, TTB, GSB, CIAF (plus generic and OFX).

## Transaction Rules

- Direction is authoritative for flow logic.
- Human-facing exports may use absolute `amount`, but persisted transaction truth remains in the database with explicit direction.
- Date/time must remain traceable to source row and source sheet.
- Reconciliation never rewrites evidence; it only classifies verification state.

## Duplicate Prevention Rules

- File duplicates use SHA-256 hash comparison.
- If a file with the same SHA-256 hash already exists, the upload is rejected with a reference to the existing file.
- Statement-batch duplicates use batch fingerprints.
- Transaction duplicates use transaction fingerprints and deterministic similarity classes.
- Duplicate grouping is additive and reviewable.

## Re-processing Rules

- Re-processing a parser run deletes all prior data from that run (transactions, batches, accounts, duplicates, alerts) before re-running.
- The parser_run record itself is preserved with updated timestamps.
- Re-processing creates fresh pipeline output, not incremental patches.

## Alert System Rules

The alert system derives findings from graph analysis. Seven detection rules are available:

1. `repeated_transfers` -- repeated large transfers between the same pair
2. `fan_in_accounts` -- many sources funneling into one account
3. `fan_out_accounts` -- one account distributing to many targets
4. `circular_paths` -- money returning to origin through intermediaries
5. `pass_through_behavior` -- accounts that receive and immediately forward
6. `high_degree_hubs` -- accounts with unusually many counterparties
7. `repeated_counterparties` -- high-frequency interactions with same counterparty

Rules:
- Each rule can be individually enabled/disabled.
- Minimum severity and confidence thresholds are configurable.
- Alerts are investigative signals only; they do not modify transactions or confirm graph edges.
- Alerts may be auto-flagged for review when `auto_flag_review` is enabled.

## Threat Hunting Patterns

Five pattern detectors are available for proactive threat hunting:

1. `smurfing` -- multiple deposits just below reporting thresholds (structuring)
2. `layering` -- rapid movement of funds through multiple accounts
3. `rapid_movement` -- high-velocity transfers within short time windows
4. `dormant_activation` -- long-inactive accounts suddenly active
5. `round_tripping` -- funds departing and returning to origin

Rules:
- Patterns are run on-demand, not automatically during intake.
- Findings include full traceability back to source transactions.
- Pattern results are advisory; they require analyst review.

## Match Rules

- Confirmed matches may become firm graph edges.
- Suggested matches must remain reversible.
- Rejected matches must not leak into confirmed graph output.

## Review Rules

- Transaction correction requires audit log entry.
- Account correction requires audit log entry.
- Review decisions must preserve reviewer, timestamp, and note.

## Export Rules

- Graph node IDs and edge IDs must be deterministic.
- i2-friendly exports must not present inferred links as confirmed.
- Human-facing exports use:
  - `DD MM YYYY`
  - comma-formatted amounts
  - no negative sign in separated transaction-category sheets
- STR and CTR regulatory exports follow Thai AMLO templates.

## Authentication and Authorization Rules

- Authentication uses JWT tokens with configurable secret (`BSIE_JWT_SECRET`).
- Default roles: `admin`, `analyst`.
- Auth can be disabled via environment for local desktop use.
- A default admin user is created on first startup if no users exist.
- Admin-only operations: user management, database reset/restore, backup settings.
- All authenticated endpoints enforce role checks when auth is enabled.

## Internationalization Rules

- Thai is the primary UI language (`th.json`).
- English is the fallback language (`en.json`).
- All user-facing labels and messages go through react-i18next.
- Backend error messages remain in English for log readability.

## Platform Rules

- Reset and restore require explicit confirmation phrases.
- Restore preview must be available before destructive restore.
- Scheduled backups must be configurable and reviewable.
- Backup retention must delete only surplus backup artifacts, never live evidence or exports.
- Rate limiting is enforced on all API endpoints via slowapi.
- Request body size is capped at 50 MB.
- Security headers (X-Frame-Options, X-Content-Type-Options, etc.) are set on every response.
