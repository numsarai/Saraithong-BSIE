# BSIE Graph Foundation Phase 1

> Updated for BSIE v4.0 -- the graph foundation is now fully integrated into the runtime via `routers/graph.py`, `services/graph_analysis_service.py`, the LinkChart UI, and the alert/threat-hunting subsystems.

Phase 1 adds the internal graph foundation without changing BSIE parsing or
normalization.

## Input Contract

The graph layer consumes finalized BSIE normalized transactions only.

Required upstream steps:
- mapping applied
- normalization completed
- classification completed
- links built (`from_account` / `to_account`)
- overrides applied
- schema enforced
- reconciliation annotated

The graph layer must not:
- parse raw files
- detect bank formats
- remap columns
- recalculate normalization rules

## Foundation Outputs

Phase 1 writes:
- `nodes.csv`
- `nodes.json`
- `edges.csv`
- `edges.json`
- `aggregated_edges.csv`
- `aggregated_edges.json`
- `derived_account_edges.csv`
- `derived_account_edges.json`
- `graph_manifest.json`

`derived_account_edges.csv` is the compact relationship layer derived from
aggregated transaction flow where both endpoints are known full account nodes.

The graph export layer is intentionally dual-format. CSV stays analyst-friendly
and spreadsheet-friendly, while the JSON companions are used by downstream
automation and API-facing consumers.

## Traceability

Every graph layer must preserve:
- source file
- batch id
- row number
- transaction id
- normalized record id or stable transaction key

In practice, this is carried through the existing BSIE transaction fields and
`lineage_json`, then projected into edge and node lineage payloads.

## Service Boundary

Phase 1 introduces a lightweight builder service:
- [`/Users/saraithong/Documents/bsie/services/graph_builder_service.py`](/Users/saraithong/Documents/bsie/services/graph_builder_service.py)

That service:
- accepts finalized normalized transactions
- optionally accepts match candidates
- returns a typed `GraphBuildResult`
- delegates graph transformation to the shared deterministic graph builder

The current runtime also has a graph-analysis service boundary on top of the
foundation:
- [`/Users/saraithong/Documents/bsie/services/graph_analysis_service.py`](/Users/saraithong/Documents/bsie/services/graph_analysis_service.py)

That higher layer:
- loads graph-ready transactions and matches from persisted BSIE records
- builds and caches graph bundles for short-lived repeated analyst queries
- feeds the API and Investigation Admin graph views
- keeps graph analytics additive rather than changing persisted transaction truth

## Current Runtime Shape

The graph foundation is no longer just an export-time helper. It now supports:

- export jobs through [`/Users/saraithong/Documents/bsie/services/export_service.py`](/Users/saraithong/Documents/bsie/services/export_service.py)
- graph analysis APIs in [`/Users/saraithong/Documents/bsie/app.py`](/Users/saraithong/Documents/bsie/app.py)
- Investigation Admin graph browsing in [`/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.tsx`](/Users/saraithong/Documents/bsie/frontend/src/components/InvestigationDesk.tsx)

Primary API surfaces built on this foundation:
- `/api/graph-analysis`
- `/api/graph/nodes`
- `/api/graph/edges`
- `/api/graph/derived-edges`
- `/api/graph/findings`
- `/api/graph/neighborhood/{node_id}`
- `/api/graph/neo4j-status`
- `/api/graph/neo4j-sync`

Graph requests are capped by the runtime graph-analysis service to preserve UI
responsiveness and avoid unbounded load.

## Rollback

If Phase 1 needs to be reverted:
1. remove `derived_account_edges.csv` expectations from export summaries/tests
2. revert `core/graph_domain.py`
3. revert `services/graph_builder_service.py`
4. revert derived-edge generation in `core/graph_export.py`

The existing `nodes.csv`, `edges.csv`, `aggregated_edges.csv`, and
`graph_analysis.*` outputs can remain independently.
