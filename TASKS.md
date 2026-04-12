# BSIE Tasks

> Updated for BSIE v4.0

## 1. Data Intake

- Ingest Excel (.xlsx, .xls), OFX, PDF, and image files
- 8 Thai bank configs: BBL, BAY, KBANK, KTB, SCB, TTB, GSB, CIAF (plus generic and OFX)
- Auto-detect bank format via keywords, strong headers, and body_keywords
- Column mapping with analyst confirmation gate
- SHA-256 file deduplication on upload
- Bulk folder intake with parallel processing
- File metadata verification and evidence storage

## 2. Processing Pipeline (14 Steps)

The pipeline runs per-account through `pipeline/process_account.py`:

1. Load and detect sheet/header
2. Bank detection and config selection
3. Column mapping (auto + analyst confirm)
4. Raw row extraction and preservation
5. Normalization to standard schema
6. Classification (income/expense/transfer)
7. Link building (from_account / to_account)
8. Override application
9. Reconciliation annotation
10. Duplicate detection (transaction fingerprint)
11. Account resolution and registry update
12. Graph export (nodes, edges, manifests)
13. Suspicious analytics (7 rules)
14. Output packaging (CSV, XLSX, JSON, i2)

## 3. Network Analysis

- **Link Chart**: Cytoscape.js interactive graph with node/edge exploration
- **SNA (Social Network Analysis)**: degree centrality, betweenness, clustering
- **Cross-Account Analysis**: multi-account flow comparison
- **Account Flow Graph**: per-account inflow/outflow visualization
- **Fund Flow Tracing**: path-finding between accounts
- **PromptPay Graph**: PromptPay-specific network analysis
- **Graph neighborhoods**: drill into node connections with configurable depth
- **Neo4j sync**: optional push to Neo4j for advanced graph queries

## 4. Alert and Anomaly Detection

- 7 graph-based alert rules (repeated transfers, fan-in, fan-out, circular, pass-through, hubs, repeated counterparties)
- 5 threat hunting patterns (smurfing, layering, rapid movement, dormant activation, round-tripping)
- Configurable severity and confidence thresholds
- Alert dashboard with summary statistics
- Auto-flag for analyst review

## 5. Report Generation

- Excel workbook exports (per-account, cross-account)
- PDF case reports via report templates
- i2 Analyst's Notebook exports:
  - Direct chart: `i2_chart.anx`
  - Import package: `i2_import_spec.ximp` + `i2_import_transactions.csv`
- STR/CTR regulatory exports (Thai AMLO format)
- Graph analysis exports (JSON, XLSX, CSV)
- Period comparison reports

## 6. Investigation Workspace (13 Tabs)

The InvestigationDesk provides:

1. **Database** -- status, backup/restore, settings
2. **Files** -- uploaded file registry with metadata
3. **Parser Runs** -- run history, re-processing
4. **Accounts** -- account registry, holder info, review
5. **Search** -- full transaction search with filters
6. **Alerts** -- alert dashboard, rule config, review
7. **Cross-Account** -- multi-account analysis
8. **Link Chart** -- interactive graph explorer
9. **Timeline** -- temporal aggregation and visualization
10. **Duplicates** -- duplicate group review
11. **Matches** -- match candidate review
12. **Audit** -- audit log and learning feedback
13. **Exports** -- export job management

## 7. Security and Authentication

- JWT-based authentication with role-based access (admin, analyst)
- Rate limiting on all API endpoints
- Security headers middleware
- 50 MB request body limit
- CORS restricted to configured origins
- Password hashing with bcrypt
- Configurable auth disable for local desktop use

## 8. Platform Operations

- SQLite-based local persistence (SQLAlchemy 2)
- Automated scheduled backups
- Backup retention management
- Database reset/restore with preview
- Case tagging and annotation
- Job queue with serialized background processing
- Auto-insights generation after pipeline completion

## 9. Engineering Backlog

- Expand PDF/image intake coverage for more bank formats
- Add E2E tests for critical investigation flows
- Add per-table restore if investigation need appears
- Expand threat hunting pattern library
- Add case-level correlation rules
