# BSIE – Bank Statement Intelligence Engine

**v3.0** · FastAPI · React · SQLAlchemy · Investigation Platform

BSIE is now a persistent, investigation-grade bank statement intelligence platform. It preserves original evidence, stores normalized transactions in a database, detects duplicate uploads and transaction overlap, generates counterparty match candidates, records audit history for manual review, and still preserves the existing CSV/XLSX/i2-style output workflow for manual analysis.

## Ownership

- Owner: ร้อยตำรวจเอกณัฐวุฒิ สาหร่ายทอง
- Developer: ร้อยตำรวจเอกณัฐวุฒิ สาหร่ายทอง
- Contact: ๐๙๖๗๗๖๘๗๕๗

---

## Features

- **Auto Bank Detection** — Scores and identifies SCB, KBANK, BBL, KTB, BAY, TTB, GSB, BAAC from file content
- **Smart Column Mapping** — 3-tier matching (exact → substring → fuzzy) with self-learning profile memory
- **14-Step Pipeline** — Normalisation, NLP enrichment, transaction classification, link building, entity deduplication
- **Persistent Evidence Store** — Uploaded files, parser runs, raw rows, normalized transactions, accounts, duplicate groups, match candidates, review decisions, and audit logs are stored in the database
- **Duplicate Detection** — Detects duplicate files by SHA-256, repeated statement batches by batch fingerprint, and repeated transactions by transaction fingerprint and deterministic similarity rules
- **Account Registry** — Reuses subject and counterparty accounts across uploads using strict account normalization rules
- **Deterministic Learning Loop** — Reuses bank fingerprints, mapping profiles, remembered account names, and review-derived learning signals without mutating raw evidence
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

Repository clones are intended for developers. Generated installers, smoke-test
screenshots, local databases, and runtime data should stay out of the repo and
are treated as local artifacts.
If someone only needs the app, they should use packaged installers/releases
instead of cloning the source repository.

### Prerequisites

- Python `3.12`
- Node.js LTS + `npm`
- macOS only: `create-dmg` if you want a DMG
- Windows only: Inno Setup 6 if you want a Windows installer

**1. Clone and create a local environment**
```bash
git clone <your-repo-url>
cd bsie
python3.12 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip setuptools wheel
./.venv/bin/python -m pip install -r requirements.txt
cd frontend && npm install && cd ..
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
./.venv/bin/alembic upgrade head
```

Runtime startup also creates tables automatically for local continuity, but Alembic is the canonical schema path.

**4. Run in development mode**
```bash
./dev.sh
```

Or run backend/frontend manually:
```bash
./.venv/bin/python app.py
cd frontend && npm run dev
```

Development URLs:

- App: `http://127.0.0.1:6776`
- API: `http://127.0.0.1:8757/api`
- Health: `http://127.0.0.1:8757/health`

**5. Run tests**
```bash
./.venv/bin/pytest tests -q
cd frontend && npm test && npm run build
```

**6. Build a desktop app (optional)**
```bash
bash build.sh
```

On macOS this produces `dist/BSIE.app`. If `create-dmg` is installed, use:
```bash
bash build.sh --dmg
```

For a Windows machine handoff or fresh Windows setup, see
[`/Users/saraithong/Documents/bsie/installer/windows/windows-handoff.md`](/Users/saraithong/Documents/bsie/installer/windows/windows-handoff.md).

---

## Documentation Map

- Architecture: [`/Users/saraithong/Documents/bsie/ARCHITECTURE.md`](/Users/saraithong/Documents/bsie/ARCHITECTURE.md)
- Agent roles and ownership rules: [`/Users/saraithong/Documents/bsie/AGENTS.md`](/Users/saraithong/Documents/bsie/AGENTS.md)
- Domain constraints: [`/Users/saraithong/Documents/bsie/DOMAIN_RULES.md`](/Users/saraithong/Documents/bsie/DOMAIN_RULES.md)
- Frontend structure: [`/Users/saraithong/Documents/bsie/frontend/README.md`](/Users/saraithong/Documents/bsie/frontend/README.md)
- Multi-agent orchestration guide: [`/Users/saraithong/Documents/bsie/docs/architecture/agent-orchestration.md`](/Users/saraithong/Documents/bsie/docs/architecture/agent-orchestration.md)
- Subagent checklists and prompt templates: [`/Users/saraithong/Documents/bsie/docs/architecture/subagent-checklists.md`](/Users/saraithong/Documents/bsie/docs/architecture/subagent-checklists.md)
- Installer guide: [`/Users/saraithong/Documents/bsie/installer/README.md`](/Users/saraithong/Documents/bsie/installer/README.md)

Subagent work in BSIE should follow the current chokepoints of the codebase, not generic backend/frontend splits. In practice, the safest default is one backend owner for [`/Users/saraithong/Documents/bsie/app.py`](/Users/saraithong/Documents/bsie/app.py), one pipeline/schema owner when contracts change, one frontend owner only if UI work is needed, and one tester/reviewer.

Packaged desktop builds use a writable per-user data directory outside the app bundle:
- macOS: `~/Library/Application Support/BSIE`
- Windows: `%LOCALAPPDATA%\BSIE`
- Existing legacy installs under `Documents/BSIE` continue to work automatically

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
| `GET` | `/api/accounts/remembered-name` | Look up remembered account holder name for a normalized account number |
| `GET` | `/api/accounts/{id}` | Get account detail |
| `GET` | `/api/accounts/{id}/review` | Get review payload and merge candidates for an account |
| `GET` | `/api/transactions/search` | Search persisted transactions |
| `GET` | `/api/transactions/{id}` | Get a persisted transaction detail record |
| `GET` | `/api/graph-analysis` | Return graph analytics from normalized transactions |
| `GET` | `/api/graph/nodes` | List graph nodes for analyst review |
| `GET` | `/api/graph/edges` | List direct graph edges |
| `GET` | `/api/graph/derived-edges` | List inferred or derived graph edges |
| `GET` | `/api/graph/findings` | List suspicious graph findings |
| `GET` | `/api/graph/neighborhood/{node_id}` | Inspect a node neighborhood with findings |
| `GET` | `/api/graph/neo4j-status` | Inspect optional Neo4j sync status |
| `POST` | `/api/graph/neo4j-sync` | Push graph projection into Neo4j |
| `GET` | `/api/duplicates` | List duplicate groups |
| `POST` | `/api/duplicates/{id}/review` | Confirm/reject duplicates |
| `GET` | `/api/matches` | List transaction/account matches |
| `POST` | `/api/matches/{id}/review` | Confirm/reject match candidates |
| `POST` | `/api/transactions/{id}/review` | Apply transaction correction with audit trail |
| `POST` | `/api/accounts/{id}/review` | Apply account correction with audit trail |
| `GET` | `/api/audit-logs` | Search audit trail |
| `GET` | `/api/learning-feedback` | Retrieve learning-feedback audit signals only |
| `POST` | `/api/exports` | Create a reproducible export job |
| `GET` | `/api/export-jobs` | List export jobs |
| `GET` | `/api/case-tags` | List case tags |
| `POST` | `/api/case-tags` | Create a case tag |
| `POST` | `/api/case-tags/assign` | Assign a case tag to an object |
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
  suspicious_findings.csv ← focused analyst review cues from graph analysis
  suspicious_findings.json
  i2_chart.anx            ← direct i2 Analyst's Notebook chart export
  i2_import_transactions.csv ← companion import data for the i2 import wizard
  i2_import_spec.ximp     ← i2 import specification for the companion CSV
meta.json                 ← summary statistics + category file map
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
- IBM i2 Analyst's Notebook direct chart export (`.anx`)
- IBM i2 Analyst's Notebook import package (`.ximp + .csv`)
- the internal BSIE Graph Analysis Module

Detailed workflow notes for analysts and operators live in [`docs/architecture/i2-export-workflows.md`](docs/architecture/i2-export-workflows.md).

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

BSIE now emits two i2-ready surfaces from the same graph bundle:

- `i2_chart.anx`
  - for analysts who want to open a ready-made chart directly in Analyst's Notebook
  - includes analyst-friendly relationship edges such as `SENT_TO`, `RECEIVED_FROM`, `OWNS`, `MATCHED_TO`, and `POSSIBLE_SAME_AS`
  - excludes aggregate rows and bookkeeping-only lineage edges like `APPEARS_IN`
  - uses the same stable node IDs as the CSV graph export
- `i2_import_spec.ximp` + `i2_import_transactions.csv`
  - for the i2 import wizard or `SeriesImport.exe`
  - focuses on transaction flow edges only (`SENT_TO`, `RECEIVED_FROM`) so imported cards stay readable and transaction-centric
  - preserves evidence-oriented fields such as transaction IDs, file IDs, parser runs, batch IDs, source files, sheets, and row numbers as import attributes

Both i2 outputs are generated from the same deterministic `nodes.csv` and `edges.csv` bundle so the direct-chart path and import-wizard path stay aligned.

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

This repository is proprietary and is not released under an open-source
license. No right to use, copy, modify, distribute, sublicense, or
commercialize BSIE is granted without prior written permission from the owner.

See [LICENSE](/Users/saraithong/Documents/bsie/LICENSE) for the full terms.
