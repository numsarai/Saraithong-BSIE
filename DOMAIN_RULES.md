# BSIE Domain Rules

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

## Transaction Rules

- Direction is authoritative for flow logic.
- Human-facing exports may use absolute `amount`, but persisted transaction truth remains in the database with explicit direction.
- Date/time must remain traceable to source row and source sheet.
- Reconciliation never rewrites evidence; it only classifies verification state.

## Duplicate Rules

- File duplicates use SHA-256.
- Statement-batch duplicates use batch fingerprints.
- Transaction duplicates use transaction fingerprints and deterministic similarity classes.
- Duplicate grouping is additive and reviewable.

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

## Platform Rules

- Reset and restore require explicit confirmation phrases.
- Restore preview must be available before destructive restore.
- Scheduled backups must be configurable and reviewable.
- Backup retention must delete only surplus backup artifacts, never live evidence or exports.
