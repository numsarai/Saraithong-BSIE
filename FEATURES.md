# BSIE Features Reference (v4.0)

## Data Intake

| Feature | Details |
|---------|---------|
| Auto Bank Detection | 8 Thai banks detected by header structure, keywords, body content |
| Smart Column Mapping | 3-tier fuzzy matching with self-learning profile memory |
| File Formats | Excel (.xlsx/.xls), OFX, PDF (text + scanned), Images (JPG/PNG/BMP) |
| OCR | EasyOCR with Thai + English language support |
| Duplicate Prevention | SHA-256 hash dedup — same file reuses existing record |
| Re-process Choice | Upload same file → choose "View Results" or "Re-process with new mapping" |

## Processing Pipeline (14 Steps)

1. Load file (multi-format)
2. Detect bank (8 configs + body keywords)
3. Detect columns (fuzzy alias matching)
4. Load mapping memory (profile reuse)
5. Apply column mapping
6. Normalize data (date/amount/direction parsing)
7-8. Account parsing + description extraction
9. NLP enrichment (Thai names, phones, National IDs, PromptPay)
10. Classify transactions (IN_TRANSFER/OUT_TRANSFER/DEPOSIT/WITHDRAW)
11. Build links (from → to accounts)
12. Apply manual overrides
13. Build entity list
14. Export Account Package

## Visualization

| Component | Technology | Features |
|-----------|-----------|----------|
| Account Flow Graph | Cytoscape.js | Radial graph, green (IN) / red (OUT), 3 layouts, click-to-detail |
| Link Chart (mini i2) | Cytoscape.js | Multi-hop expand, 5 layouts, conditional formatting, pin, SNA metrics |
| Timeline Chart | Recharts | Bar + dot modes, day/week/month granularity |
| Time Wheel | Custom SVG | Hour × Day heatmap, detect unusual activity patterns |
| Dashboard | React | Stats, flows, recent activity, top accounts |

## Network Analysis

| Feature | Details |
|---------|---------|
| Multi-hop Expand | Click node → load neighbors → expand unlimited depth |
| 5 Layout Modes | Circle, Spread, Compact, Hierarchy (tree), Peacock (concentric) |
| SNA Metrics | Degree centrality, betweenness centrality, closeness centrality |
| Conditional Formatting | Node size by flow amount, border color by risk/alerts |
| Edge Labels Toggle | Show/hide amounts on edges |
| Multi-select + Hide | Select nodes → hide/show for cleaner view |
| Pin + Focus History | Lock important nodes, track exploration path |
| Graph Annotations | Notes + tags on nodes, persisted in DB |
| Workspace | Save/load entire chart state (expanded nodes, positions, filters) |

## Alert System

| Rule | Detects | Default Threshold |
|------|---------|-------------------|
| repeated_transfers | Same account pair transfers | ≥3 txns, ≥1,000 THB |
| fan_in_accounts | Money from multiple sources | ≥5 txns, ≥3 sources, ≥5,000 THB |
| fan_out_accounts | Money to multiple targets | ≥5 txns, ≥3 targets, ≥5,000 THB |
| circular_paths | Bidirectional flow A⇄B | ≥4 combined txns |
| pass_through_behavior | Account as intermediary | In/out ratio ≤25% gap |
| high_degree_hubs | Highly connected accounts | ≥6 connections, ≥10,000 THB |
| repeated_counterparties | Same counterparty across days | ≥4 txns, ≥2 days |

## Statistical Anomaly Detection

| Method | How It Works |
|--------|-------------|
| Z-score | Flag transactions >Nσ from account mean |
| IQR | Flag amounts outside Q1-1.5×IQR to Q3+1.5×IQR |
| Benford's Law | Compare first-digit distribution to expected |
| Moving Average | Flag deviations from 30-transaction rolling average |

## Cross-Account Analysis

| Feature | Details |
|---------|---------|
| Fund Flow | View inbound sources + outbound targets for any account |
| Pairwise Transactions | All transactions between two specific accounts |
| BFS Path Finder | Trace money path A→B→C→D (max 4 hops) |
| Bulk Cross-Match | Match transactions across all accounts simultaneously |
| Multi-period Comparison | Compare metrics between two date ranges |

## Export & Reporting

| Format | Contents |
|--------|---------|
| Excel Report (.xlsx) | 14+ sheets, TH Sarabun New, color-coded, auto-filter, =SUM/=COUNTA formulas |
| PDF Report (.pdf) | Cover page, stats, counterparties, alerts, transactions, signature blocks |
| i2 Chart (.anx) | Analyst's Notebook compatible chart |
| i2 Import (.csv + .ximp) | CSV data + XML spec for i2 import |
| Report Templates | Configurable sections, analysis criteria, custom thresholds |
| CSV exports | transactions, entities, links, reconciliation, graph data |

## Security & Infrastructure

| Feature | Details |
|---------|---------|
| Authentication | JWT tokens, user roles (admin/analyst/viewer), optional enforcement |
| i18n | Thai/English, ~500 translation keys, TH Sarabun New font |
| Audit Trail | Every data mutation logged with who/when/what/why |
| Chain of Custody | Full object history via /api/audit-trail/{type}/{id} |
| CORS | Configured for frontend dev + production |
| Request Timing | Log slow requests >1s, X-Process-Time-Ms header |
| MaxBodySize | Reject uploads >50 MB |
| CI/CD | GitHub Actions: lint, type check, test, build |
| Tests | 244 total (212 backend pytest + 32 frontend vitest) |
