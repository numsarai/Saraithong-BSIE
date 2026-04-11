# Graph Export Architecture

## Purpose

BSIE maintains two graph-oriented export surfaces:

1. machine-friendly CSV graph exports
2. analyst-friendly IBM i2-style `.anx` exports

Both now derive from the same shared graph builder in [`core/graph_export.py`](../../core/graph_export.py).

BSIE also includes an internal graph-analysis layer in [`core/graph_analysis.py`](../../core/graph_analysis.py) that consumes the same normalized transaction outputs and shared graph model.

In the live runtime, persisted transactions and matches are loaded through
[`services/export_service.py`](../../services/export_service.py) and
[`services/graph_analysis_service.py`](../../services/graph_analysis_service.py),
so graph exports, graph APIs, and Investigation Admin all reuse the same
deterministic graph bundle path.

## Shared Schema

The shared graph layer produces:

- `nodes.csv`
- `nodes.json`
- `edges.csv`
- `edges.json`
- `aggregated_edges.csv`
- `aggregated_edges.json`
- `derived_account_edges.csv`
- `derived_account_edges.json`
- `graph_manifest.json`

### Node identity

Node IDs are typed and deterministic:

- `ACCOUNT:<digits>`
- `PARTIAL_ACCOUNT:<digits>`
- `ENTITY:<hash>`
- `BANK:<slug>`
- `STATEMENT_BATCH:<id-or-hash>`
- `TRANSACTION:<stable-key>`
- `CASH:UNSPECIFIED`
- `UNKNOWN_COUNTERPARTY`

Transaction node IDs intentionally avoid database primary keys. They are derived from evidence-level attributes such as file identity, source row, transaction fingerprint, or stable transaction-record hints.

### Edge identity

Edge IDs are deterministic and type-aware:

- `FLOW:<transaction-key>`
- `OWNS:<hash>`
- `APPEARS_IN:...`
- `MATCH:<hash>`
- `FLOW_AGG:<hash>`
- `DERIVED_FLOW:<hash>`

Relationship edges are deduplicated by `edge_id` so repeated supporting rows merge support metadata instead of creating unstable duplicates.

## Safety Semantics

### Confirmed vs inferred links

- Statement-derived flow edges use `assertion_status=derived_from_statement`
- Suggested transaction/account matches use `edge_type=POSSIBLE_SAME_AS`
- Confirmed matches use `edge_type=MATCHED_TO`
- Manual confirmations use `assertion_status=manual_confirmed`
- Rejected matches are excluded from graph export

### Direction rules

Flow direction is always based on `from_account -> to_account`, not raw bank column naming:

- incoming transfer: counterparty -> subject
- outgoing transfer: subject -> counterparty
- deposit: cash -> subject
- withdraw: subject -> cash

## Lineage

Transaction-level edges carry:

- `file_id`
- `parser_run_id`
- `statement_batch_id`
- `date`
- `time`
- `amount_display`
- `source_row_number`
- `source_sheet`
- `source_file`
- `reference_no`
- `lineage_json`

Node rows also carry aggregated lineage so analysts can trace where a participant came from across files and rows.

The graph manifest records schema/version/count information for bundle
consumers. It is the contract that lets CSV/JSON exports and graph analytics
agree on the same graph shape.

## i2 Export Strategy

BSIE now emits two i2-facing outputs from the same graph bundle:

1. direct chart export via [`core/export_anx.py`](../../core/export_anx.py)
2. import-package export via [`core/export_i2_import.py`](../../core/export_i2_import.py)

The ANX exporter intentionally exports a simplified subgraph:

- includes `OWNS`, `SENT_TO`, `RECEIVED_FROM`, `MATCHED_TO`, `POSSIBLE_SAME_AS`
- excludes aggregate rows
- excludes bookkeeping-only lineage edges such as `APPEARS_IN`

This keeps the chart readable while preserving the richer CSV graph layer for downstream tools and secondary processing.

The i2 import package uses a more import-friendly transaction surface:

- writes `i2_import_transactions.csv`
- writes `i2_import_spec.ximp`
- only includes transaction-flow edges (`SENT_TO`, `RECEIVED_FROM`)
- maps transaction lineage fields into import attributes so analysts can inspect file, parser-run, batch, sheet, and row provenance after import

This gives analysts two stable workflows:

- open `i2_chart.anx` when they want a ready-made chart immediately
- import `i2_import_spec.ximp` when they want i2 to build cards and layout from the companion CSV inside the Analyst's Notebook import flow

During implementation the generated `.anx` and `.ximp` outputs were validated with the Windows .NET XML parser against the real i2 schema files bundled with Analyst's Notebook 9. That check matters because the legacy macOS XML tooling does not fully understand every regex/import construct in those older XSD files.

## Graph Analysis Module

The BSIE Graph Analysis Module is an additive internal extension, not a separate system.

It consumes:

1. normalized BSIE transaction outputs
2. optional persisted match suggestions / confirmations
3. the shared graph builder output

It produces:

- `graph_analysis.json`
- `graph_analysis.xlsx`
- `suspicious_findings.csv`
- `suspicious_findings.json`
- API payloads from `/api/graph-analysis`
- Investigation Admin summaries in the `Graph Analysis` tab

Current analytics are deterministic and lineage-safe:

- graph overview counts
- node and edge type distributions
- top nodes by degree
- top nodes by flow value
- connected components across business nodes
- review candidate nodes with reason codes
- lineage coverage summary

The analysis layer intentionally excludes bookkeeping-only `APPEARS_IN` edges from business connectivity metrics so graph structure remains useful to analysts.

## Service-Layer Runtime Notes

The live runtime adds a short-TTL cache in
[`services/graph_analysis_service.py`](../../services/graph_analysis_service.py)
for repeated graph exploration requests. This keeps the graph views responsive
without changing any persisted evidence or graph truth.

The graph-analysis service also applies hard query caps for analyst safety:
- default graph query limit: `2000`
- hard max: `5000`
- default neighborhood node limit: `14`
- default neighborhood edge limit: `24`

## Extension Guidance

To extend the graph safely:

1. add new node/edge types in the shared graph builder first
2. update `graph_manifest.json` metadata
3. keep `edges.csv` backward compatible by adding columns rather than renaming existing ones
4. decide whether the new edge belongs in direct ANX, the import package, or only in CSV
5. add regression tests for schema, direction, lineage, and assertion status
