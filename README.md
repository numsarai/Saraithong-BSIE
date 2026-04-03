# BSIE – Bank Statement Intelligence Engine

**v3.0** · FastAPI · React · SQLAlchemy · Investigation Platform

BSIE is now a persistent, investigation-grade bank statement intelligence platform. It preserves original evidence, stores normalized transactions in a database, detects duplicate uploads and transaction overlap, generates counterparty match candidates, records audit history for manual review, and still preserves the existing CSV/XLSX/i2-style output workflow for manual analysis.

---

## Features

- **Auto Bank Detection** — Scores and identifies SCB, KBANK, BBL, KTB, BAY, TTB, GSB, BAAC from file content
- **Smart Column Mapping** — 3-tier matching (exact → substring → fuzzy) with self-learning profile memory
- **14-Step Pipeline** — Normalisation, NLP enrichment, transaction classification, link building, entity deduplication
- **Persistent Evidence Store** — Uploaded files, parser runs, raw rows, normalized transactions, accounts, duplicate groups, match candidates, review decisions, and audit logs are stored in the database
- **Duplicate Detection** — Detects duplicate files by SHA-256, repeated statement batches by batch fingerprint, and repeated transactions by transaction fingerprint and deterministic similarity rules
- **Account Registry** — Reuses subject and counterparty accounts across uploads using strict account normalization rules
- **Match Suggestions** — Generates exact-account, reference, mirrored-transfer, probable-internal-transfer, and fuzzy-name candidates with reversible confidence scores
- **Review + Audit Trail** — Manual reviews and corrections create review decisions and append-only audit log entries
- **Pattern-Based NLP** — Extracts Thai/English names, phone numbers, PromptPay markers, embedded account numbers — no ML dependencies
- **Hybrid Classifier** — 4-rule priority chain producing typed transactions with confidence scores
- **Manual Overrides** — CRUD API for correcting relationship flows, persisted across runs
- **Export Package** — CSV + Excel outputs for transactions, entities, and links per account
- **Bulk Folder Intake** — Process a whole case folder of statement files and generate a case summary
- **Investigation Workspace** — Files, parser runs, accounts, transactions, duplicates, matches, audit logs, and reproducible export jobs are accessible from the UI and API

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
| Persistence | SQLAlchemy 2, SQLModel compatibility layer, Alembic |
| Matching | RapidFuzz (difflib fallback) |
| Utilities | python-dateutil |

---

## Quick Start

**1. Install dependencies**
```bash
pip install -r requirements.txt
```

**2. Configure local runtime**
```bash
cp .env.example .env
```

BSIE now runs only against the local SQLite database at `bsie.db`. No PostgreSQL, Redis, or external worker runtime is required for normal local use.

Optional operational settings:

- `PORT=8757`
- `BSIE_ENABLE_AUTO_BACKUP=1`
- `BSIE_BACKUP_INTERVAL_HOURS=24`
- `BSIE_AUTO_BACKUP_FORMAT=json`
- `BSIE_BACKUP_POLL_SECONDS=60`

**3. Create or upgrade the local schema**
```bash
alembic upgrade head
```

Runtime startup also creates tables automatically for local continuity, but Alembic is the canonical schema path.

**4. Run the server**
```bash
python app.py
```

The app starts at **http://127.0.0.1:8757**

**5. Run tests**
```bash
PYTHONPATH=$PWD pytest tests -q
cd frontend && npm test && npm run build
```

---

## Workflow

```
Upload Excel / OFX
    ↓
Store original evidence + hash
    ↓
Auto-detect bank + columns
    ↓
Confirm/edit column mapping  (profile saved for reuse)
    ↓
Create parser run + persist raw source rows
    ↓
Run 14-step background pipeline
    ↓
Persist statement batch + accounts + normalized transactions
    ↓
Generate duplicate groups + match candidates
    ↓
Poll job status → view results
    ↓
Review / search / export
```

### Bulk Folder Intake

BSIE can process a whole folder of statements in one run for case-level intake.
It infers the subject account conservatively from the filename first, then from
explicit workbook header labels when available.

```bash
curl -X POST http://127.0.0.1:8757/api/process-folder \
  -H "Content-Type: application/json" \
  -d '{
    "folder_path": "/absolute/path/to/case-folder",
    "recursive": false
  }'
```

Case summary outputs are written to `/data/output/bulk_runs/{run_id}/`:
- `bulk_summary.csv`
- `bulk_summary.xlsx`
- `bulk_summary.json`

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
| `POST` | `/api/process-folder` | Process a local folder of statements and return a case summary |
| `GET` | `/api/job/{job_id}` | Poll job status and logs |
| `GET` | `/api/results/{account}` | Retrieve paginated transactions |
| `GET` | `/api/files` | List persisted file evidence |
| `GET` | `/api/files/{id}` | Get file detail + parser runs |
| `GET` | `/api/admin/db-status` | Check DB backend, schema tables, and key record counts |
| `GET` | `/api/admin/backups` | List DB backups and confirmation phrases |
| `GET` | `/api/admin/backup-settings` | Read the effective scheduled backup settings |
| `GET` | `/api/admin/backups/{backup_name}/preview` | Preview restore impact vs current DB |
| `POST` | `/api/admin/backup-settings` | Update scheduled backup enablement, interval, and format |
| `POST` | `/api/admin/backup` | Create a JSON backup of the active BSIE database |
| `POST` | `/api/admin/reset` | Reset the active DB after explicit confirmation and automatic safety backup |
| `POST` | `/api/admin/restore` | Restore a selected backup after explicit confirmation and automatic pre-restore backup |
| `GET` | `/api/parser-runs` | List parser runs |
| `POST` | `/api/parser-runs/{id}/reprocess` | Reprocess a historical parser run |
| `GET` | `/api/accounts` | Search account registry |
| `GET` | `/api/accounts/{id}` | Get account detail |
| `GET` | `/api/transactions/search` | Search persisted transactions |
| `GET` | `/api/duplicates` | List duplicate groups |
| `POST` | `/api/duplicates/{id}/review` | Confirm/reject duplicates |
| `GET` | `/api/matches` | List transaction/account matches |
| `POST` | `/api/matches/{id}/review` | Confirm/reject match candidates |
| `GET` | `/api/audit-logs` | Search audit trail |
| `POST` | `/api/exports` | Create a reproducible export job |
| `GET` | `/api/export-jobs` | List export jobs |
| `POST` | `/api/override` | Add / update a relationship override |
| `DELETE` | `/api/override/{id}` | Remove an override |
| `GET` | `/api/overrides` | List all overrides |
| `GET` | `/api/profiles` | List saved mapping profiles |
| `GET` | `/api/download/{account}/{path}` | Download output file |
| `GET` | `/api/download-export/{job_id}/{path}` | Download export job output |
| `GET` | `/api/download-backup/{backup_name}` | Download a database backup |
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
  nodes.csv               ← graph nodes with stable typed IDs
  edges.csv               ← graph edges with lineage + review safety
  aggregated_edges.csv    ← aggregated flow edges for graph tooling
  graph_manifest.json     ← graph schema/version + counts
  graph_analysis.json     ← BSIE graph analytics from normalized transactions
  graph_analysis.xlsx     ← analyst-friendly workbook for graph analytics
  i2_chart.anx            ← simplified i2-friendly XML chart export
  meta.json               ← summary statistics
```

Bulk runs also write a case-level summary to `/data/output/bulk_runs/{run_id}/`.

Database-backed export jobs write to `/data/exports/{job_id}/`.

Human-facing transaction exports now use investigation-friendly formatting:

- dates as `DD MM YYYY`
- money with thousands separators
- exported `amount` values as absolute values, with direction carried by the flow/type fields instead of a minus sign

## Duplicate Detection

BSIE uses three additive duplicate layers:

1. **File duplicate detection**
   - SHA-256 on the uploaded bytes
   - duplicates are tagged, not silently discarded
2. **Statement batch duplicate detection**
   - account + date range + transaction count + opening/closing balances + debit/credit totals
   - exact and overlapping batches are flagged on the batch record
3. **Transaction duplicate detection**
   - account + datetime + amount + direction + normalized description + reference + counterparty account + balance
   - statuses: `exact_duplicate`, `probable_duplicate`, `overlap_duplicate`, `similar_conflict`, `unique`

## Matching Logic

Transaction linking is deterministic and reviewable:

- `exact_account_match`
- `reference_match`
- `mirrored_transfer_match`
- `probable_internal_transfer`
- `fuzzy_name_match`

Suggested matches remain reversible until manually confirmed.

## Audit Trail

BSIE preserves:

- original file metadata and hash
- raw row JSON per parser run
- normalized transactions with lineage JSON
- review decisions
- audit log entries for field changes and manual review actions

Manual corrections never erase the raw evidence layer.

## Example Import Flow

1. Upload a statement through the UI or `POST /api/upload`
2. Confirm the column mapping
3. Start processing with `POST /api/process`
4. Poll `/api/job/{job_id}`
5. Review persisted records in the Investigation workspace

## Database Admin

The Investigation workspace now acts as a lightweight database admin for case operations:

- inspect DB backend and schema status
- browse files, parser runs, accounts, transactions, duplicates, matches, and audit logs
- filter transactions with a query builder
- correct account and transaction records through audit-safe review endpoints
- reprocess a historical parser run
- create database backups
- create JSON safety backups before reset/restore work
- enable/disable scheduled backups from the UI
- adjust backup interval from the UI without editing `.env`
- preview restore impact before replacing current data
- download existing backups
- reset the active database with an explicit confirmation phrase and automatic safety backup
- restore a selected backup with an explicit confirmation phrase and automatic pre-restore backup
- scheduled automatic backups can default from `.env` and then be overridden in the database

## Example Export Flow

1. Open the Investigation workspace
2. Create an export job for transactions, duplicates, unresolved matches, corrected transactions, or graph output
3. Download the generated files from `/api/download-export/{job_id}/{path}`

## Graph Export and i2 Safety

BSIE graph exports now use one shared deterministic schema across:

- per-account package exports
- database-backed graph export jobs
- IBM i2-style ANX output
- the internal BSIE Graph Analysis Module

### Graph node schema

`nodes.csv` uses stable typed IDs such as:

- `ACCOUNT:1234567890`
- `PARTIAL_ACCOUNT:1234`
- `ENTITY:...`
- `BANK:...`
- `STATEMENT_BATCH:...`
- `TRANSACTION:...`
- `CASH:UNSPECIFIED`

Each node row includes:

- `node_id`
- `node_type`
- `label`
- `identity_value`
- confidence and review status
- source transaction/file/parser-run lineage

### Graph edge schema

`edges.csv` includes:

- stable `edge_id`
- `source` / `target`
- `edge_type`
- `assertion_status`
- `confidence_score`
- `review_status`
- transaction, batch, parser run, file, row, sheet, and source file lineage

`aggregated_edges.csv` summarizes transaction-level flow edges without changing the underlying transaction edges.

### Graph analysis module

BSIE also computes a reusable internal graph-analysis layer from the same normalized transactions and shared graph schema.

Outputs:

- `graph_analysis.json`
- `graph_analysis.xlsx`

Analytics currently include:

- graph/node/edge counts
- node and edge type distributions
- top nodes by degree
- top nodes by flow value
- connected components
- review candidate nodes
- lineage coverage counts
- suspicious findings
- focused neighborhood graph retrieval for the investigation UI
- optional Neo4j sync for downstream graph persistence

This keeps the pipeline consistent:

`raw import -> parsing -> mapping -> normalization -> validation -> structured output -> graph modeling -> graph analytics -> graph export/API/UI`

### Safety rules

- Transaction flow direction always follows `from_account -> to_account`.
- Suggested matches export as `POSSIBLE_SAME_AS`.
- Only manually confirmed matches export as `MATCHED_TO` with `assertion_status=manual_confirmed`.
- Rejected matches are excluded.
- Aggregate files are additive only and never replace the transaction-level evidence rows.

### i2 export behavior

`i2_chart.anx` is intentionally simpler than the CSV graph export:

- includes analyst-friendly relationship edges such as `SENT_TO`, `RECEIVED_FROM`, `OWNS`, `MATCHED_TO`, and `POSSIBLE_SAME_AS`
- excludes aggregate rows and bookkeeping-only lineage edges like `APPEARS_IN`
- uses the same stable node IDs as the CSV graph export

### Optional Neo4j integration

BSIE can now sync the same shared graph bundle into Neo4j without changing parser or normalization behavior.

Key env flags:

- `BSIE_ENABLE_NEO4J_EXPORT=1`
- `NEO4J_URI=bolt://localhost:7687`
- `NEO4J_USER=neo4j`
- `NEO4J_PASSWORD=...`
- `NEO4J_DATABASE=neo4j`

Behavior:

- graph sync is optional and additive
- graph nodes and edges are built from normalized BSIE transactions already persisted in the platform
- suspicious findings can also be synced as `SuspiciousFinding` nodes with `FLAGS` relationships
- if Neo4j is not configured, BSIE still runs normally

### AI classification guardrails

BSIE keeps heuristic classification as the baseline and only applies LLM-based enrichment when explicitly enabled.

Key env flags:

- `BSIE_ENABLE_LLM_CLASSIFICATION=1`
- `LLM_API_KEY=...`
- `LLM_MODEL_NAME=gpt-4o-mini`
- `BSIE_LLM_MIN_CONFIDENCE=0.85`
- `BSIE_LLM_MAX_TRANSACTIONS=250`

Safety behavior:

- heuristic classification remains the default
- AI is disabled unless explicitly enabled
- AI results below the configured confidence threshold do not override the heuristic result
- AI-driven type divergence can mark the transaction for analyst review
- exported transaction rows preserve provenance fields such as `classification_source`, `classification_reason`, `heuristic_transaction_type`, and `ai_transaction_type`

---

## Transaction Types

`IN_TRANSFER` · `OUT_TRANSFER` · `DEPOSIT` · `WITHDRAW` · `FEE` · `SALARY` · `IN_UNKNOWN` · `OUT_UNKNOWN`

---

## Project Structure

```
bsie/
├── app.py                    ← FastAPI server + all endpoints
├── alembic/                  ← schema migration scripts
├── database.py               ← legacy compatibility facade
├── requirements.txt
├── config/                   ← Bank configs (scb.json, kbank.json)
├── persistence/              ← SQLAlchemy models, schemas, engine/session config
├── services/                 ← ingestion, duplicate, matching, audit, review, search, export services
├── pipeline/
│   └── process_account.py    ← existing 14-step orchestrator with persistence integration
├── core/                     ← parser, normalizer, reconciliation, exporter, analytics modules
├── data/
│   ├── evidence/             ← stored original file evidence
│   ├── output/               ← legacy account packages + bulk runs
│   └── exports/              ← DB-backed export job output
├── docs/architecture/        ← upgrade and compatibility notes
├── frontend/                 ← React analyst UI
└── tests/                    ← backend regression + persistence tests
```

## Additional Documentation

- [`docs/architecture/persistence-upgrade.md`](docs/architecture/persistence-upgrade.md)
- [`docs/architecture/graph-export.md`](docs/architecture/graph-export.md)
- [`config_registry/README.md`](config_registry/README.md)

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
