# BSIE Graph Suspicious Analytics Phase 2

Phase 2 adds a reusable suspicious-analytics rule engine on top of the Phase 1
graph foundation.

## Purpose

The rule engine highlights graph patterns that may deserve analyst review while
preserving BSIE's evidence-first workflow.

It does **not**:
- modify parsing
- modify normalization
- change transaction truth
- promote inferred relationships to confirmed facts

## Rule Engine Position

Pipeline:

`raw import -> parsing -> mapping -> normalization -> validation -> structured output -> graph modeling -> suspicious analytics`

The rule engine consumes:
- finalized normalized transactions
- business graph nodes
- derived account-to-account edges
- graph degree/flow summaries
- optional persisted match suggestions and confirmations routed through the
  graph bundle service layer

## Implemented Rules

- `repeated_transfers`
- `fan_in_accounts`
- `fan_out_accounts`
- `circular_paths`
- `pass_through_behavior`
- `high_degree_hubs`
- `repeated_counterparties`

## Config Structure

The config is a dictionary keyed by rule name.

Each rule supports:
- `enabled`
- threshold values specific to the rule
- `severity`

Example:

```json
{
  "repeated_transfers": {
    "enabled": true,
    "min_transaction_count": 3,
    "min_total_amount_abs": 1000.0,
    "min_avg_confidence": 0.7,
    "severity": "medium"
  }
}
```

## Traceability

Each finding includes:
- `transaction_ids`
- `statement_batch_ids`
- `parser_run_ids`
- `file_ids`
- `source_row_numbers`
- `source_sheets`
- `source_files`
- `traceability_json`

This allows analysts to move from a suspicious graph pattern back to the exact
normalized records and source evidence.

In the current runtime, these findings surface through:
- [`/Users/saraithong/Documents/bsie/services/graph_analysis_service.py`](/Users/saraithong/Documents/bsie/services/graph_analysis_service.py)
- `/api/graph-analysis`
- `/api/graph/findings`
- `/api/graph/neighborhood/{node_id}`
- the `Graph Analysis` tab in Investigation Admin

## Sample Finding Shape

```json
{
  "finding_id": "FINDING:fan_in_accounts:ABCDEF1234567890",
  "rule_type": "fan_in_accounts",
  "severity": "high",
  "confidence_score": 0.85,
  "subject_node_ids": "ACCOUNT:1111111111|ACCOUNT:2222222222|ACCOUNT:3333333333",
  "subject_edge_ids": "DERIVED_FLOW:...",
  "transaction_ids": "TX-1|TX-2|TX-3",
  "summary": "High fan-in into ACCOUNT:1111111111",
  "reason": "The account receives many transactions from multiple distinct source accounts.",
  "reason_codes": "fan_in|multi_source",
  "evidence_json": "...",
  "thresholds_json": "...",
  "traceability_json": "..."
}
```

## Extension Notes

Safe future additions:
- velocity rules based on narrower time windows
- channel-specific suspicious rules
- bank-specific heuristic overlays
- case-level correlation rules
- person/company/device-aware relationship rules

When adding rules:
1. keep them deterministic
2. preserve traceability
3. keep inferred findings separate from confirmed conclusions
4. add a focused unit test per rule

## Current Safety Boundaries

Suspicious findings are investigative signals only. They do not:

- edit persisted transactions
- change duplicate or match review state
- create confirmed graph edges by themselves
- bypass analyst review in Investigation Admin
