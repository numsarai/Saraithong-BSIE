# BSIE – Bank Statement Intelligence Engine

**v2.0** · FastAPI · Python 3.9+ · Thai Bank Support

BSIE is a web-based platform for processing Thai bank account statements (Excel format). It automatically detects the bank and column structure, runs a 14-step enrichment pipeline, and exports structured transaction, entity, and link data for financial analysis.

---

## Features

- **Auto Bank Detection** — Scores and identifies SCB, KBANK, BBL, KTB, BAY, TTB, GSB, BAAC from file content
- **Smart Column Mapping** — 3-tier matching (exact → substring → fuzzy) with self-learning profile memory
- **14-Step Pipeline** — Normalisation, NLP enrichment, transaction classification, link building, entity deduplication
- **Pattern-Based NLP** — Extracts Thai/English names, phone numbers, PromptPay markers, embedded account numbers — no ML dependencies
- **Hybrid Classifier** — 4-rule priority chain producing typed transactions with confidence scores
- **Manual Overrides** — CRUD API for correcting relationship flows, persisted across runs
- **Export Package** — CSV + Excel outputs for transactions, entities, and links per account

---

## Supported Banks

| Key | Bank |
|-----|------|
| `scb` | Siam Commercial Bank |
| `kbank` | Kasikornbank |
| `bbl` | Bangkok Bank |
| `ktb` | Krung Thai Bank |
| `bay` | Krungsri (Bank of Ayudhya) |
| `ttb` | TMB Thanachart Bank |
| `gsb` | Government Savings Bank |
| `baac` | Bank for Agriculture and Cooperatives |

---

## Tech Stack

| Layer | Libraries |
|-------|-----------|
| Web | FastAPI, Uvicorn, Jinja2, python-multipart |
| Data | Pandas, Openpyxl, xlrd |
| Matching | RapidFuzz (difflib fallback) |
| Utilities | python-dateutil |

---

## Quick Start

**1. Install dependencies**
```bash
pip install -r requirements.txt
```

**2. Run the server**
```bash
python app.py
```

The app starts at **http://127.0.0.1:5001**

---

## Workflow

```
Upload Excel
    ↓
Auto-detect bank + columns
    ↓
Confirm/edit column mapping  (profile saved for reuse)
    ↓
Run 14-step background pipeline
    ↓
Poll job status → view results
    ↓
Download CSV / Excel outputs
```

---

## Pipeline Steps

| # | Step | Description |
|---|------|-------------|
| 1 | Load Excel | Read file, detect sheet and header row |
| 2 | Detect Bank | Score all bank configs by column names + cell content |
| 3 | Detect Columns | Map actual columns to logical fields |
| 4 | Suggest Mapping | Merge detection with saved memory profile |
| 5 | Apply Mapping | Validate and apply confirmed column mapping |
| 6 | Normalize | Clean amounts, parse dates, standardize fields |
| 7 | Parse Accounts | Extract and classify account numbers from cells |
| 8 | Extract from Text | Find embedded account numbers in descriptions |
| 9 | NLP Enrichment | Extract names, phones, PromptPay; hint at transaction type |
| 10 | Classify | 4-rule hybrid classifier → transaction type + confidence |
| 11 | Build Links | Create `from_account → to_account` edges |
| 12 | Apply Overrides | Re-map flows from manual override store |
| 13 | Build Entities | Deduplicate all participants into entity table |
| 14 | Export | Write transactions, entities, links to CSV + Excel + meta.json |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Web UI |
| `POST` | `/api/upload` | Upload Excel, get bank + column suggestions |
| `POST` | `/api/mapping/confirm` | Confirm column mapping and save profile |
| `POST` | `/api/process` | Start pipeline (returns `job_id`) |
| `GET` | `/api/job/{job_id}` | Poll job status and logs |
| `GET` | `/api/results/{account}` | Retrieve paginated transactions |
| `POST` | `/api/override` | Add / update a relationship override |
| `DELETE` | `/api/override/{id}` | Remove an override |
| `GET` | `/api/overrides` | List all overrides |
| `GET` | `/api/profiles` | List saved mapping profiles |
| `GET` | `/api/download/{account}/{path}` | Download output file |
| `GET` | `/api/banks` | List available bank configs |

---

## Output Files

For each processed account the pipeline writes to `/data/output/{account_number}/`:

```
raw/
  original.xlsx           ← copy of input
processed/
  transactions.csv/.xlsx  ← full transaction detail (50+ columns)
  entities.csv/.xlsx      ← unique participants with metadata
  links.csv/.xlsx         ← transaction graph edges
  meta.json               ← summary statistics
```

---

## Transaction Types

`IN_TRANSFER` · `OUT_TRANSFER` · `DEPOSIT` · `WITHDRAW` · `FEE` · `SALARY` · `IN_UNKNOWN` · `OUT_UNKNOWN`

---

## Project Structure

```
bsie/
├── app.py                    ← FastAPI server + all endpoints
├── main.py                   ← CLI entry point
├── requirements.txt
├── config/                   ← Bank configs (scb.json, kbank.json)
├── core/                     ← Processing modules
│   ├── bank_detector.py
│   ├── column_detector.py
│   ├── loader.py
│   ├── normalizer.py
│   ├── account_parser.py
│   ├── nlp_engine.py
│   ├── classifier.py
│   ├── link_builder.py
│   ├── entity.py
│   ├── override_manager.py
│   ├── mapping_memory.py
│   └── exporter.py
├── pipeline/
│   └── process_account.py    ← 14-step orchestrator
├── overrides/
│   └── overrides.json        ← Persisted manual overrides
├── mapping_profiles/         ← Self-learning column profiles
├── data/                     ← Input uploads + output results
├── templates/                ← Jinja2 HTML UI
├── static/                   ← CSS + JS
└── utils/                    ← date_utils, text_utils
```

---

## Adding a New Bank

Create a JSON config in `/config/{bank_key}.json`:

```json
{
  "bank_name": "My Bank",
  "sheet_index": 0,
  "header_row": 0,
  "skip_rows": [],
  "column_mapping": {
    "date":                 ["Date", "วันที่"],
    "time":                 ["Time", "เวลา"],
    "description":          ["Description", "รายการ"],
    "amount":               ["Amount", "จำนวนเงิน"],
    "balance":              ["Balance", "ยอดคงเหลือ"],
    "counterparty_account": ["Counterparty Account", "บัญชีคู่โอน"],
    "counterparty_name":    ["Counterparty Name", "ชื่อคู่โอน"]
  },
  "currency": "THB",
  "amount_mode": "signed"
}
```

Set `"amount_mode"` to `"signed"` (single column, positive/negative) or `"debit_credit"` (separate debit and credit columns).

---

## License

MIT
