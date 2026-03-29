---
name: bsie-pipeline
description: Use this skill when the task is to process one or more bank statement Excel files into structured, normalized transaction records for financial analysis, investigation, reconciliation, or downstream entity/link analysis. Trigger this skill when the user asks to ingest .xlsx or .xls statements, detect the issuing bank, extract ledger rows, standardize dates/amounts/accounts/descriptions, or return machine-readable transaction output. Do not use this skill for PDF-only statements, image-only statements, narrative reporting without file processing, or generic spreadsheet cleanup unrelated to bank transactions.
---

# bsie-pipeline

Process bank statement Excel files into deterministic, traceable, normalized transaction output.

This skill is designed for financial investigation work. Accuracy, auditability, and controlled failure are more important than speed.

## Operating Rules

- Treat every source file as evidentiary input. Preserve raw values and traceability.
- Be deterministic. Prefer explicit rules over heuristics whenever possible.
- Never invent transactions, accounts, names, dates, amounts, or banks.
- Never silently drop ambiguous rows. Classify them as rejected, unknown, or needs-review with a reason.
- Keep raw input, normalized output, and validation issues separate.
- If confidence is low at any stage, return a structured warning instead of guessing.

## Inputs

Required inputs:

- `file_path`: absolute or workspace-relative path to a bank statement Excel file.

Optional inputs:

- `subject_account`: account under investigation, if already known.
- `subject_name`: account holder or case label, if already known.
- `bank_hint`: expected bank key if the operator already knows the bank.
- `sheet_hint`: sheet name or index if a specific sheet must be used.
- `header_row_hint`: expected header row if known.
- `timezone`: timezone for date normalization. Default to the case or workspace timezone.
- `currency_hint`: expected currency if the file omits it.

Accepted file types:

- `.xlsx`
- `.xls`

Reject or escalate:

- password-protected workbooks
- corrupted workbooks
- CSV files unless the user explicitly wants CSV handling
- PDFs, screenshots, or scanned images

## Outputs

Return one structured result object with these sections:

- `status`: `success`, `partial_success`, or `failed`
- `source`: file metadata and selected sheet/header information
- `bank_detection`: detected bank, confidence, evidence, and fallback path used
- `transactions`: normalized transaction records
- `rejected_rows`: rows that were inspected but not converted into valid transactions
- `warnings`: non-fatal issues
- `errors`: fatal issues
- `summary`: row counts and key normalization statistics

Minimum transaction schema:

```json
{
  "row_id": 1,
  "source_row_number": 2,
  "transaction_date": "2026-03-01",
  "transaction_time": "14:23:00",
  "amount": -1250.00,
  "currency": "THB",
  "direction": "OUT",
  "balance": 50231.55,
  "description_raw": "TRF TO 1234567890 SOMCHAI",
  "description_normalized": "TRF TO 1234567890 SOMCHAI",
  "counterparty_account": "1234567890",
  "counterparty_name": "SOMCHAI",
  "bank": "SCB",
  "account_number_subject": "9876543210",
  "reference": "",
  "channel": "",
  "transaction_type": "OUT_TRANSFER",
  "normalization_notes": [],
  "confidence": 0.98
}
```

Rules for output construction:

- Preserve numeric precision for money values.
- Use ISO date format: `YYYY-MM-DD`.
- Use 24-hour time format when time exists: `HH:MM:SS`.
- Keep `description_raw` exactly as observed except for safe string conversion.
- Use `null` for unknown structured values, not guessed placeholders.
- Include `normalization_notes` for any inferred or repaired field.

## Workflow

Execute the workflow in this exact order.

### 1. Load file

Objective:

- Read the workbook safely and identify the transaction-bearing sheet and header row.

Procedure:

1. Validate that the file exists and has an accepted Excel extension.
2. Open the workbook in read mode without modifying source content.
3. Enumerate all sheets.
4. Score sheets by evidence of transaction data:
   - presence of date-like values
   - presence of amount, debit, or credit columns
   - presence of description or balance columns
   - non-empty tabular density
5. Select the best sheet.
6. Detect the header row by scanning the first candidate rows for banking column aliases.
7. Load the selected sheet using the detected header row.
8. Preserve the original row index or derive a stable `source_row_number`.

Edge case handling:

- If multiple sheets score similarly, choose the one with the strongest date-plus-amount evidence and record a warning.
- If no sheet contains likely transaction data, fail with `status=failed`.
- If the header row is ambiguous, use the earliest row with the highest alias coverage and record the ambiguity.
- If merged cells or blank spacer rows exist, keep scanning until a usable header is found.
- If the workbook contains summary sheets plus detail sheets, prefer detail sheets over cover sheets.

Failure conditions:

- file missing
- unreadable workbook
- no usable sheet
- no usable header row

### 2. Detect bank

Objective:

- Determine the originating bank using deterministic evidence from the workbook.

Procedure:

1. If `bank_hint` is provided, validate it against workbook evidence before trusting it.
2. Build a detection evidence set from:
   - workbook filename
   - selected sheet name
   - header labels
   - first rows of cell content
   - known bank-specific keywords and aliases
3. Score all supported bank configurations.
4. Select the highest-scoring bank only if it clears the confidence threshold.
5. If no bank clears threshold, use a controlled fallback such as `generic` and mark the result low-confidence.

Detection rules:

- Prefer explicit bank names over weak column-pattern matches.
- Prefer configuration-backed banks over informal keyword guesses.
- Return the score table or top candidates in `bank_detection.evidence`.

Edge case handling:

- If two banks tie closely, do not pick arbitrarily. Return low confidence and include both candidates.
- If the file format is structurally valid but bank-specific evidence is weak, proceed with `generic` mapping only if the extraction path remains auditable.
- If `bank_hint` conflicts with detected evidence, preserve both and record a warning.

Failure conditions:

- no supported bank and no safe generic path

### 3. Extract transactions

Objective:

- Convert workbook rows into raw transaction candidates without normalization loss.

Procedure:

1. Determine the statement format:
   - single signed amount
   - debit/credit split
   - sender/receiver dual-account format
   - bank-specific transfer log format
2. Map physical columns to logical fields:
   - date
   - time
   - description
   - amount or debit/credit
   - balance
   - counterparty account
   - counterparty name
   - sender account or receiver account when available
   - channel or reference fields when available
3. Iterate row by row after the header.
4. Skip only rows that are structurally empty.
5. Build a raw candidate record for each non-empty row, preserving raw strings.
6. Mark rows that appear to be opening balance, closing balance, page totals, or non-transaction notes.
7. Send non-transaction rows to `rejected_rows` with a reason instead of deleting them silently.

Extraction rules:

- One worksheet row becomes at most one transaction candidate unless the bank format explicitly requires row combination.
- Never merge adjacent rows unless there is a deterministic bank-specific rule for continuation lines.
- Preserve source row numbers exactly.

Edge case handling:

- If debit and credit are both populated, flag the row for review unless the bank format defines the meaning.
- If a row has a date but no amount, reject it with reason `missing_amount`.
- If a row has an amount but no date, retain it only if neighboring evidence proves the date is carried forward; otherwise reject it.
- If the statement repeats headers mid-sheet, reject those rows as `repeated_header`.
- If duplicate rows exist, do not deduplicate automatically unless the operator explicitly requests deduplication.

Failure conditions:

- required transaction columns cannot be mapped
- zero extractable transaction candidates

### 4. Normalize data

Objective:

- Transform raw candidates into a consistent transaction schema while preserving traceability.

Procedure:

1. Normalize dates into ISO format.
2. Normalize times into `HH:MM:SS` when present.
3. Normalize amounts:
   - remove thousand separators
   - handle parentheses for negatives
   - handle debit or credit polarity rules
   - store signed numeric values
4. Normalize balances using the same numeric rules.
5. Normalize text fields with whitespace cleanup only. Do not remove meaningful identifiers.
6. Parse subject and counterparty account numbers where present.
7. Extract account fragments embedded in descriptions when explicit account columns are absent.
8. Determine direction from signed amount or bank-specific debit/credit logic.
9. Standardize bank names and transaction type labels.
10. Attach confidence and `normalization_notes` for each inferred field.

Normalization rules:

- Use signed amounts: incoming positive, outgoing negative.
- Preserve the original raw description separately from the normalized description.
- Do not convert unknown names into guessed identities.
- If the counterparty account equals the subject account, classify as possible self-transfer and note it.
- If balance is absent for the entire statement, keep it as `null` unless a deterministic case rule allows computed balance.

Edge case handling:

- If date parsing yields multiple valid interpretations, prefer the bank-locale format and record the rule used.
- If amounts contain currency symbols or Thai notation, strip symbols but preserve the numeric meaning.
- If time is embedded inside description text, extract it only if the dedicated time column is absent and the match is unambiguous.
- If account numbers are masked or partial, store partial values in a distinct field or note rather than inventing the full account.
- If names are numeric-only or equal to system filler values, do not treat them as validated human names.

Failure conditions:

- amount cannot be parsed for every candidate
- date cannot be normalized for every retained candidate

### 5. Return structured result

Objective:

- Return a complete, machine-readable result suitable for audit, downstream enrichment, or manual review.

Procedure:

1. Assemble normalized transactions in original statement order.
2. Populate `rejected_rows` with row number, raw content snapshot, and rejection reason.
3. Populate `warnings` with all non-fatal ambiguities.
4. Populate `errors` only when the run is failed or partially failed.
5. Build a summary:
   - total rows scanned
   - transaction rows extracted
   - rows rejected
   - bank detected
   - confidence distribution
   - missing-field counts
6. Return the final object without extra narration unless the user explicitly asks for prose analysis.

Completion rules:

- If at least one transaction is valid and at least one row was rejected or ambiguous, return `partial_success`.
- If all expected transaction rows are normalized cleanly, return `success`.
- If no reliable transaction output can be produced, return `failed`.

## Validation Checklist

Before returning results, verify all of the following:

- file path and selected sheet are recorded
- bank detection result is recorded with evidence
- every transaction has `source_row_number`
- every transaction has normalized `amount`
- every retained transaction has normalized `transaction_date`
- no rejected row was silently discarded
- no guessed account or guessed name was introduced
- warnings and errors are separated correctly

## Edge Case Catalogue

Handle these cases explicitly:

- multi-sheet workbooks
- repeated header rows inside data
- summary rows mixed with transactions
- blank separator rows
- debit and credit split formats
- signed amount formats
- dual-account transfer layouts
- missing time column
- missing balance column
- masked or partial account numbers
- bank not confidently identified
- conflicting bank evidence
- duplicated transactions
- files containing Thai and English labels in the same sheet
- corrupted numeric formatting such as commas, currency symbols, parentheses, or stray spaces

## Deterministic Decision Policy

When multiple interpretations are possible:

1. Prefer explicit bank configuration rules.
2. Prefer column-based evidence over free-text inference.
3. Prefer preserving `unknown` over guessing.
4. Prefer returning `partial_success` over hiding uncertainty.
5. Prefer rejection with reason over silent omission.

## Suggested Extensions

Additional skills that pair well with this system:

- `bsie-bank-config-authoring`: create or refine bank-specific column maps and format rules.
- `bsie-statement-validation`: audit extracted transactions for gaps, duplicates, running-balance breaks, and suspicious formatting anomalies.
- `bsie-entity-resolution`: resolve counterparties, aliases, phone numbers, PromptPay identifiers, and account relationships across statements.
- `bsie-transaction-classification`: classify normalized rows into transfer, cash, fee, salary, loan, merchant, and internal movement categories.
- `bsie-link-analysis`: convert normalized transactions into account-to-account graph edges for investigation.
- `bsie-evidence-packaging`: export normalized output, validation logs, and metadata into court-ready or analyst-ready packages.
- `bsie-override-management`: apply investigator-approved corrections without mutating original source evidence.
