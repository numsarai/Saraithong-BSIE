# BSIE Graph Foundation Phase 1

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
- `edges.csv`
- `aggregated_edges.csv`
- `derived_account_edges.csv`
- `graph_manifest.json`

`derived_account_edges.csv` is the compact relationship layer derived from
aggregated transaction flow where both endpoints are known full account nodes.

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
- `services/graph_builder_service.py`

That service:
- accepts finalized normalized transactions
- optionally accepts match candidates
- returns a typed `GraphBuildResult`
- delegates graph transformation to the shared deterministic graph builder

## Rollback

If Phase 1 needs to be reverted:
1. remove `derived_account_edges.csv` expectations from export summaries/tests
2. revert `core/graph_domain.py`
3. revert `services/graph_builder_service.py`
4. revert derived-edge generation in `core/graph_export.py`

The existing `nodes.csv`, `edges.csv`, `aggregated_edges.csv`, and
`graph_analysis.*` outputs can remain independently.
