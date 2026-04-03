import pandas as pd

from core.reconciliation import reconcile_balances


def test_reconcile_balances_marks_verified_statement_sequence():
    df = pd.DataFrame([
        {"transaction_id": "TXN-1", "date": "2026-03-01", "amount": 100.0, "balance": 1000.0},
        {"transaction_id": "TXN-2", "date": "2026-03-02", "amount": -50.0, "balance": 950.0},
        {"transaction_id": "TXN-3", "date": "2026-03-03", "amount": 25.0, "balance": 975.0},
    ])

    result = reconcile_balances(df)

    assert result.summary["status"] == "VERIFIED"
    assert result.summary["matched_rows"] == 2
    assert result.summary["mismatched_rows"] == 0
    assert result.transactions["balance_check_status"].tolist() == [
        "OPENING_REFERENCE",
        "MATCH",
        "MATCH",
    ]


def test_reconcile_balances_marks_mismatch_when_balance_breaks_sequence():
    df = pd.DataFrame([
        {"transaction_id": "TXN-1", "date": "2026-03-01", "amount": 100.0, "balance": 1000.0},
        {"transaction_id": "TXN-2", "date": "2026-03-02", "amount": -50.0, "balance": 960.0},
    ])

    result = reconcile_balances(df)

    assert result.summary["status"] == "FAILED"
    assert result.summary["mismatched_rows"] == 1
    assert result.transactions.loc[1, "balance_check_status"] == "MISMATCH"
    assert result.transactions.loc[1, "balance_difference"] == 10.0


def test_reconcile_balances_marks_inferred_when_statement_has_no_balance():
    df = pd.DataFrame([
        {"transaction_id": "TXN-1", "date": "2026-03-01", "amount": 100.0, "balance": 100.0},
        {"transaction_id": "TXN-2", "date": "2026-03-02", "amount": -25.0, "balance": 75.0},
    ])
    df["balance"] = pd.Series([None, None], dtype="float64")

    result = reconcile_balances(df)

    assert result.summary["status"] == "INFERRED"
    assert set(result.transactions["balance_check_status"].tolist()) == {"INFERRED"}
    assert set(result.transactions["balance_source"].tolist()) == {"INFERRED"}


def test_reconcile_balances_detects_chronology_issues_when_sorting_reduces_mismatches():
    df = pd.DataFrame([
        {"transaction_id": "TXN-1", "date": "2026-03-01", "time": "01:00:00", "amount": 100.0, "balance": 100.0, "row_number": 2},
        {"transaction_id": "TXN-2", "date": "2026-03-01", "time": "03:00:00", "amount": -50.0, "balance": 150.0, "row_number": 3},
        {"transaction_id": "TXN-3", "date": "2026-03-01", "time": "02:00:00", "amount": 50.0, "balance": 150.0, "row_number": 4},
    ])

    result = reconcile_balances(df)

    assert result.summary["status"] == "FAILED"
    assert result.summary["chronology_issue_detected"] is True
    assert result.summary["chronological_mismatched_rows"] < result.summary["mismatched_rows"]
    assert result.summary["mismatches_reduced_by_sorting"] == 1
    assert result.summary["recommended_check_mode"] == "chronological"
    assert "out_of_order_rows" in result.summary["suspected_scenarios"]
    assert any("ไม่เรียงตามเวลา" in note for note in result.summary["guidance_th"])


def test_reconcile_balances_reports_small_rounding_drift_rows():
    df = pd.DataFrame([
        {"transaction_id": "TXN-1", "date": "2026-03-01", "time": "01:00:00", "amount": 100.0, "balance": 1000.0},
        {"transaction_id": "TXN-2", "date": "2026-03-01", "time": "02:00:00", "amount": -50.0, "balance": 950.32},
    ])

    result = reconcile_balances(df)

    assert result.summary["rounding_drift_rows"] == 1
    assert result.summary["material_mismatched_rows"] == 0
    assert any("small drift values" in note for note in result.summary["notes"])
    assert "rounding_or_minor_adjustment" in result.summary["suspected_scenarios"]
