# BSIE Architecture (v4.0)

## Runtime Shape

BSIE is a local-first FastAPI + React 19 financial intelligence platform with:

- 21 API routers serving 103+ endpoints
- 27 service modules for business logic
- 20 database models in SQLite (WAL mode)
- React 19 SPA with Cytoscape.js + Recharts visualization
- i18n support (Thai/English)

## System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Frontend (React 19)                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │Dashboard │ │ LinkChart│ │ Timeline │ │TimeWheel │       │
│  │          │ │(Cytoscape│ │(Recharts)│ │(Heatmap) │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Steps    │ │ Invest.  │ │FlowGraph │ │ Entity   │       │
│  │ 1-5      │ │ Desk     │ │          │ │ Profile  │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│  Zustand store │ react-i18next │ React Query                 │
└──────────────────────────┬───────────────────────────────────┘
                           │ REST API (JSON)
┌──────────────────────────┴───────────────────────────────────┐
│                  Backend (FastAPI)                             │
│                                                               │
│  ┌─ Middleware ──────────────────────────────────────────┐    │
│  │ CORS │ Timing │ MaxBodySize │ Auth (JWT optional)     │    │
│  └───────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌─ Routers (21) ───────────────────────────────────────┐    │
│  │ ingestion │ search │ alerts │ fund_flow │ analytics   │    │
│  │ graph │ review │ admin │ banks │ reports │ dashboard  │    │
│  │ auth │ annotations │ workspace │ exports │ ...        │    │
│  └───────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌─ Services (27) ──────────────────────────────────────┐    │
│  │ alert_service │ fund_flow_service │ anomaly_detection │    │
│  │ sna_service │ auth_service │ report_service           │    │
│  │ bulk_matching │ period_comparison │ report_template    │    │
│  │ audit_service │ review_service │ search_service │ ... │    │
│  └───────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌─ Core Pipeline ──────────────────────────────────────┐    │
│  │ loader → bank_detector → column_detector → normalizer │    │
│  │ → nlp_engine → classifier → link_builder → entity     │    │
│  │ → graph_export → graph_analysis → graph_rules         │    │
│  │ → exporter → export_anx → export_i2_import            │    │
│  │ → pdf_loader → image_loader (OCR)                     │    │
│  └───────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌─ Persistence (SQLAlchemy 2) ─────────────────────────┐    │
│  │ 20 models: FileRecord, Account, Transaction,          │    │
│  │ TransactionMatch, Entity, Alert, User,                │    │
│  │ GraphAnnotation, ParserRun, StatementBatch, ...       │    │
│  │                                                       │    │
│  │ SQLite (WAL) + Alembic migrations                     │    │
│  └───────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

## Data Flow

```
Upload (.xlsx/.xls/.ofx/.pdf/.jpg)
    ↓
persist_upload() → SHA-256 dedup → evidence storage
    ↓
[Duplicate?] → Yes: show choice dialog (view results / re-process)
              → No: continue
    ↓
detect_bank() → 8 bank configs with keywords + headers + body patterns
    ↓
detect_columns() → fuzzy match column aliases
    ↓
14-Step Pipeline:
  1. Load file (Excel/OFX/PDF/Image)
  2. Detect bank
  3. Detect columns
  4. Load mapping memory
  5. Apply column mapping
  6. Normalize data
  7-8. Account parsing + description extraction
  9. NLP enrichment (Thai names, phones, National IDs, PromptPay)
  10. Classify transactions (IN_TRANSFER/OUT_TRANSFER/DEPOSIT/WITHDRAW)
  10.5. Optional AI classification guardrails
  11. Build links (from_account → to_account)
  12. Apply manual overrides
  13. Build entity list
  14. Export Account Package
    ↓
Persist to DB → Generate alerts → Generate graph analysis
    ↓
Output: Excel report + CSV + i2 (ANX/XIMP) + PDF report + graph files
```

## Key Design Decisions

See [docs/adr/](docs/adr/) for Architecture Decision Records:

- **ADR-001**: SQLite — zero-config, portable, evidence-preserving
- **ADR-002**: Cytoscape.js — graph-specialized, built-in interaction
- **ADR-003**: Duplicate prevention — SHA-256 reuse, cleanup on re-process
- **ADR-004**: Thai-first i18n — fallbackLng: 'th', TH Sarabun New font

## Database Schema

20 tables. Key relationships:

```
FileRecord ← ParserRun ← StatementBatch ← Transaction
                                              ↓
Account ← AccountEntityLink → Entity    TransactionMatch
                                              ↓
Alert ← GraphAnnotation                DuplicateGroup
```

Full ERD: [docs/erd.html](docs/erd.html)

## Security

- JWT authentication (opt-in via `BSIE_AUTH_REQUIRED=true`)
- CORS middleware for frontend/backend separation
- MaxBodySize middleware (50 MB limit)
- Request timing middleware (log slow requests >1s)
- SHA-256 file integrity verification
- Audit trail for all data mutations
- No hardcoded secrets (env vars only)
