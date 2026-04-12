---
name: bsie-pipeline
description: |
  Use this skill for any task involving bank statement processing, financial transaction analysis,
  or investigation workflows in the BSIE platform. Trigger when the user asks to:
  - Ingest bank statements (Excel, OFX, PDF, or images)
  - Detect issuing banks from file content
  - Normalize and classify transactions
  - Build account-to-account flow networks
  - Detect suspicious patterns or anomalies
  - Generate investigation reports (Excel, PDF, i2 ANX)
  - Trace fund flow paths across multiple accounts
  - Analyze social network metrics (SNA)
  - Manage alerts, annotations, or workspace state

  This skill covers the full BSIE v4.0 platform — from file upload through
  graph analysis to court-ready export.
---

# bsie-pipeline

Process bank statement files into deterministic, traceable, normalized transaction output.
Build investigation-grade financial networks. Detect suspicious patterns. Generate reports.

BSIE is a financial intelligence platform for Thai police investigators, functioning as a mini i2 Analyst's Notebook.

## Operating Rules

- Treat every source file as evidentiary input. Preserve raw values and traceability.
- Be deterministic. Prefer explicit rules over heuristics.
- Never invent transactions, accounts, names, dates, amounts, or banks.
- Never silently drop rows. Classify as rejected/unknown/needs-review with a reason.
- If confidence is low, return a structured warning instead of guessing.
- Duplicate files are detected by SHA-256 hash — same file reuses existing record.
- Re-processing a file cleans up prior parser run data to prevent duplicate accumulation.

## Inputs

Required:
- `file_path`: path to bank statement file

Accepted file types:
- `.xlsx`, `.xls` — Excel bank statements
- `.ofx` — Open Financial Exchange
- `.pdf` — Text-based or scanned (auto-detected, falls back to OCR)
- `.jpg`, `.jpeg`, `.png`, `.bmp` — Images (processed via EasyOCR Thai+English)

Optional:
- `subject_account`: account under investigation
- `subject_name`: account holder name
- `bank_hint`: expected bank key (scb, kbank, bbl, ktb, bay, ttb, gsb, baac)
- `sheet_hint`: specific sheet name
- `header_row_hint`: expected header row

## Supported Banks (8)

| Key | Bank | Detection Method |
|-----|------|-----------------|
| scb | Siam Commercial Bank | Headers + column structure |
| kbank | Kasikornbank | Headers + dual-account layout |
| bbl | Bangkok Bank | Header patterns |
| ktb | Krung Thai Bank | Header + layout |
| bay | Krungsri | Direction marker format |
| ttb | TMB Thanachart Bank | Header patterns |
| gsb | Government Savings Bank | ACCOUNT_ID/TRANSDESC headers + MyMo body keywords |
| baac | Bank for Agriculture | Header patterns |

Detection uses: header keywords (strong/weak), body keywords, column alias fuzzy matching,
layout analysis (debit_credit_like, signed_amount, etc.), and bank fingerprint memory.

## 14-Step Processing Pipeline

1. **Load file** — Excel/OFX/PDF/Image with auto-format detection
2. **Detect bank** — 8 bank configs scored by header + body + layout evidence
3. **Detect columns** — 3-tier fuzzy matching (exact → substring → rapidfuzz)
4. **Load mapping memory** — reuse saved column profiles
5. **Apply column mapping** — map physical to logical fields
6. **Normalize data** — dates, amounts, directions, balances
7-8. **Account parsing** — extract accounts from descriptions
9. **NLP enrichment** — Thai names, phone numbers, National IDs (13-digit), PromptPay markers
10. **Classify transactions** — IN_TRANSFER, OUT_TRANSFER, DEPOSIT, WITHDRAW
10.5. **Optional AI classification** — LLM guardrails (disabled by default)
11. **Build links** — from_account → to_account edges
12. **Apply manual overrides** — investigator corrections
13. **Build entity list** — deduplicated counterparties
14. **Export Account Package** — Excel, CSV, i2, graph files

## Output Schema

Minimum transaction record:

```json
{
  "transaction_id": "TX:A1B2C3...",
  "date": "2026-03-01",
  "time": "14:23:00",
  "amount": -1250.00,
  "currency": "THB",
  "direction": "OUT",
  "balance": 50231.55,
  "description_raw": "TRF TO 1234567890 SOMCHAI",
  "description_normalized": "trf to 1234567890 somchai",
  "counterparty_account": "1234567890",
  "counterparty_name": "SOMCHAI",
  "bank": "SCB",
  "subject_account": "9876543210",
  "transaction_type": "OUT_TRANSFER",
  "confidence": 0.98,
  "source_file": "original.xlsx",
  "source_sheet": "Statement",
  "row_number": 5
}
```

## Export Formats

| Format | Contents |
|--------|---------|
| Excel (.xlsx) | Multi-sheet report, TH Sarabun New font, color-coded by type, auto-filter, =SUM/=COUNTA formulas |
| PDF (.pdf) | Investigation report with cover, stats, counterparty table, alerts, signature blocks |
| i2 Chart (.anx) | Analyst's Notebook compatible network chart |
| i2 Import (.csv + .ximp) | CSV data + XML spec for i2 import |
| CSV | transactions, entities, links, reconciliation, graph nodes/edges |
| OFX | Re-exported statement in OFX format |

## Network Analysis Capabilities

### Link Chart (mini i2)
- Multi-hop expansion: click node → load neighbors → expand unlimited depth
- 5 layouts: Circle, Spread, Compact, Hierarchy (tree), Peacock (concentric)
- Conditional formatting: node size by flow, color by risk
- Edge labels toggle, multi-select, pin nodes, focus history
- Graph annotations: notes + tags on nodes
- Workspace: save/load chart state

### Social Network Analysis (SNA)
- Degree centrality: who is most connected
- Betweenness centrality: who is the critical intermediary
- Closeness centrality: who can reach others fastest

### Cross-Account Analysis
- Fund flow: inbound sources + outbound targets per account
- Pairwise transactions: all transactions between two specific accounts
- BFS path finder: trace money A→B→C→D (max 4 hops)
- Bulk cross-match: match transactions across all accounts simultaneously

## Alert System (7 Detection Rules)

| Rule | Detects | Threshold |
|------|---------|-----------|
| repeated_transfers | Same pair ≥3 transfers | ≥1,000 THB |
| fan_in_accounts | Multiple sources | ≥5 txns, ≥3 sources |
| fan_out_accounts | Multiple targets | ≥5 txns, ≥3 targets |
| circular_paths | Bidirectional flow | ≥4 combined |
| pass_through_behavior | Intermediary account | ≤25% gap |
| high_degree_hubs | Highly connected | ≥6 connections |
| repeated_counterparties | Same CP across days | ≥4 txns, ≥2 days |

## Statistical Anomaly Detection

- **Z-score**: flag transactions >Nσ from mean
- **IQR**: interquartile range outliers
- **Benford's Law**: first-digit distribution check
- **Moving Average**: deviation from rolling 30-txn average

## API Architecture

21 routers, 103+ endpoints:
- ingestion, search, alerts, fund_flow, analytics, graph, review
- admin, banks, reports, dashboard, auth, annotations, workspace
- bulk, jobs, results, case_tags, overrides, exports, ui

## Validation Checklist

Before returning results, verify:
- File path and selected sheet recorded
- Bank detection with evidence documented
- Every transaction has source_row_number + normalized amount + date
- No rejected row silently discarded
- No guessed accounts or names introduced
- Warnings and errors separated
- Lineage identifiers (file_id, parser_run_id) attached
- Alerts generated from graph analysis findings

## Suggested Companion Skills

- `bsie-bank-config-authoring` — create/refine bank detection configs
- `bsie-statement-validation` — audit for gaps, duplicates, balance breaks
- `bsie-entity-resolution` — resolve counterparties, PromptPay, phone numbers
- `bsie-evidence-packaging` — court-ready export packages
