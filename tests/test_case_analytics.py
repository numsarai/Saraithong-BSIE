import json
from pathlib import Path

import pandas as pd

from core.case_analytics import compute_case_analytics, write_case_analytics


def test_case_analytics_computes_rankings_and_flags(tmp_path):
    output_dir = tmp_path / "1111111111" / "processed"
    output_dir.mkdir(parents=True)
    tx_df = pd.DataFrame([
        {"date": "2026-03-01", "amount": "100", "direction": "IN", "counterparty_account": "2222222222", "counterparty_name": "Alice"},
        {"date": "2026-03-02", "amount": "-50", "direction": "OUT", "counterparty_account": "3333333333", "counterparty_name": "Bob"},
    ])
    tx_df.to_csv(output_dir / "transactions.csv", index=False, encoding="utf-8-sig")

    summary = {
        "run_id": "20260330_030000",
        "files": [
            {
                "status": "processed",
                "account": "1111111111",
                "name": "Subject",
                "bank_name": "SCB",
                "bank_confidence": 0.6,
                "bank_ambiguous": False,
                "reconciliation_status": "FAILED",
                "output_dir": str(tmp_path / "1111111111"),
            }
        ],
    }

    analytics = compute_case_analytics(summary)
    assert analytics["overview"]["flagged_accounts"] == 1
    assert analytics["top_counterparties_by_count"][0]["counterparty_label"] == "Alice (2222222222)"
    assert analytics["fan_in_rank"][0]["subject_account"] == "1111111111"
    assert analytics["fan_out_rank"][0]["subject_account"] == "1111111111"

    run_dir = tmp_path / "bulk_runs" / "20260330_030000"
    write_case_analytics(run_dir, analytics)
    assert (run_dir / "case_analytics.json").exists()
    assert (run_dir / "case_analytics.xlsx").exists()

    saved = json.loads((run_dir / "case_analytics.json").read_text(encoding="utf-8"))
    assert saved["run_id"] == "20260330_030000"
