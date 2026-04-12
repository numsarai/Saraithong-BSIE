# BSIE – Bank Statement Intelligence Engine

**v4.0** · Financial Intelligence Platform · FastAPI · React 19 · Cytoscape.js · SQLAlchemy

BSIE is an investigation-grade financial intelligence platform for Thai police investigators. It processes bank statements from 8 Thai banks, builds transaction networks, detects suspicious patterns, and generates court-ready reports — functioning as a mini i2 Analyst's Notebook.

## Ownership

- Owner: ร้อยตำรวจเอกณัฐวุฒิ สาหร่ายทอง
- Developer: ร้อยตำรวจเอกณัฐวุฒิ สาหร่ายทอง
- Contact: ๐๙๖๗๗๖๘๗๕๗

---

## Key Capabilities

### Data Intake
- **8 Thai Banks**: SCB, KBANK, BBL, KTB, BAY, TTB, GSB, BAAC — auto-detected from file content
- **File Formats**: Excel (.xlsx/.xls), OFX, PDF (text + scanned), Images (JPG/PNG/BMP via OCR)
- **Smart Column Mapping**: 3-tier matching (exact → substring → fuzzy) with self-learning memory
- **Duplicate Prevention**: SHA-256 dedup — same file reuses existing record

### 14-Step Processing Pipeline
Normalisation → NLP enrichment (Thai names, phones, National IDs, PromptPay) → Transaction classification → Link building → Entity deduplication → Graph analysis → Alert generation → Export

### Investigation Workspace (13 tabs)
Database | Files | Parser Runs | Accounts | Search | Alerts | Cross-Account | Link Chart | Timeline | Duplicates | Matches | Audit | Exports

### Network Analysis (mini i2)
- **Multi-hop Link Chart**: Click node → expand → trace A→B→C→D
- **5 Layouts**: Circle, Spread, Compact, Hierarchy, Peacock
- **SNA Metrics**: Degree, betweenness, closeness centrality
- **Conditional Formatting**: Node size by amount, color by risk
- **Annotations + Workspace**: Notes on nodes, save/load chart state

### Alert System (7 Detection Rules)
repeated_transfers | fan_in | fan_out | circular_paths | pass_through | high_degree_hubs | repeated_counterparties

### Statistical Anomaly Detection
Z-score | IQR | Benford's Law | Moving Average

### Export & Reporting
- **Excel**: Multi-sheet, TH Sarabun New, color-coded, auto-filter, formulas
- **PDF**: Investigation report with signature blocks
- **i2**: ANX + XIMP + CSV for i2 Analyst's Notebook
- **Report Templates**: Configurable sections + analysis criteria

### Security
- JWT Authentication (BSIE_AUTH_REQUIRED env flag)
- i18n Thai/English
- 244 Tests (212 backend + 32 frontend)
- CI/CD (GitHub Actions)
- CORS + Request Timing Middleware
- Architecture Decision Records

---

## Tech Stack

| Layer | Libraries |
|-------|-----------|
| Backend | FastAPI, Uvicorn, 21 API routers, 27 services |
| Frontend | React 19, Vite, TypeScript, Tailwind CSS, Zustand |
| Visualization | Cytoscape.js, Recharts |
| Data | Pandas, Openpyxl, pdfplumber, EasyOCR |
| Database | SQLAlchemy 2, SQLite (WAL), Alembic |
| Auth | python-jose (JWT) |
| i18n | react-i18next |
| PDF | fpdf2 + TH Sarabun New |

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

## Quick Start

```bash
git clone <your-repo-url>
cd bsie
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
uvicorn app:app --host 127.0.0.1 --port 8757
```

Open http://localhost:8757

---

## Project Structure

```
bsie/
├── app.py                  # FastAPI app (thin shell, 145 lines)
├── routers/                # 21 API router modules
├── services/               # 27 business logic services
├── core/                   # Processing pipeline modules
├── persistence/            # SQLAlchemy models (20 tables)
├── pipeline/               # 14-step processing pipeline
├── frontend/src/           # React 19 + TypeScript
├── locales/                # Backend i18n
├── config/                 # Bank detection configs
├── static/fonts/           # TH Sarabun New
├── docs/adr/               # Architecture Decision Records
└── tests/                  # 212 backend tests
```

## Architecture Decision Records

- [ADR-001](docs/adr/001-sqlite-as-primary-database.md) — SQLite as primary database
- [ADR-002](docs/adr/002-cytoscape-for-graph-visualization.md) — Cytoscape.js for graph visualization
- [ADR-003](docs/adr/003-duplicate-prevention-reuse-policy.md) — Duplicate prevention policy
- [ADR-004](docs/adr/004-i18n-thai-first-architecture.md) — Thai-first i18n architecture
