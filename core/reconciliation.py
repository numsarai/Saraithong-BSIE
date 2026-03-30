"""
reconciliation.py
-----------------
Deterministic balance-reconciliation checks for normalized bank transactions.

This module separates three concepts that investigation workflows need to keep
distinct:
1. statement-provided balances
2. inferred running balances
3. verified sequential balance consistency
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


TOLERANCE = 0.01
ROUNDING_DRIFT_TOLERANCE = 0.50

RECONCILIATION_EXPORT_COLUMNS = [
    "transaction_id",
    "date",
    "time",
    "amount",
    "balance",
    "expected_balance",
    "balance_difference",
    "balance_source",
    "balance_check_status",
    "description",
    "row_number",
    "source_file",
]


@dataclass(frozen=True)
class ReconciliationResult:
    transactions: pd.DataFrame
    reconciliation: pd.DataFrame
    summary: dict[str, Any]


def _round_money(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if pd.isna(value):
        return None
    return round(float(value), 2)


def _safe_sort_timestamp(tx: pd.DataFrame) -> pd.Series:
    date_series = tx.get("date", pd.Series([""] * len(tx), index=tx.index)).fillna("").astype(str)
    time_series = tx.get("time", pd.Series([""] * len(tx), index=tx.index)).fillna("").astype(str)
    return pd.to_datetime((date_series + " " + time_series).str.strip(), errors="coerce")


def _duplicate_timestamp_count(sort_key: pd.Series) -> int:
    valid = sort_key.dropna()
    if valid.empty:
        return 0
    return int(valid.duplicated(keep=False).sum())


def _build_guidance(summary: dict[str, Any], transactions: pd.DataFrame) -> tuple[list[str], list[str], str]:
    scenarios: list[str] = []
    guidance_th: list[str] = []

    if summary.get("balance_source") == "inferred":
        scenarios.append("no_statement_balance")
        guidance_th.append("ไฟล์นี้ไม่มีคอลัมน์ยอดคงเหลือที่ตรวจสอบได้ ระบบจึงคำนวณยอดวิ่งเอง ควรใช้ผลนี้เพื่อวิเคราะห์ธุรกรรม แต่ไม่ควรใช้ยืนยัน balance ของ statement โดยตรง")

    if summary.get("chronology_issue_detected"):
        scenarios.append("out_of_order_rows")
        guidance_th.append("รายการใน statement น่าจะไม่เรียงตามเวลา ควรดูผลแบบเรียงตามเวลาและกลับไปเทียบกับไฟล์ต้นฉบับก่อนสรุปว่ามียอดผิดจริง")

    if int(summary.get("missing_time_rows", 0) or 0) > 0:
        scenarios.append("missing_or_unparseable_time")
        guidance_th.append("บางแถวไม่มีเวลา หรือเวลาแปลไม่ออก การตรวจแบบเรียงตามเวลาอาจยังไม่แม่นทั้งหมด ควรตรวจช่วงที่มีปัญหาซ้ำจาก statement ต้นฉบับ")

    if int(summary.get("duplicate_timestamp_rows", 0) or 0) > 0:
        scenarios.append("duplicate_timestamps")
        guidance_th.append("มีหลายรายการที่เวลาเดียวกัน ทำให้ลำดับภายในวินาทีนั้นอาจสลับกันได้ ควรพิจารณาจากแถวต้นฉบับร่วมด้วย")

    if int(summary.get("rounding_drift_rows", 0) or 0) > 0:
        scenarios.append("rounding_or_minor_adjustment")
        guidance_th.append("มีแถวที่ต่างกันเพียงเศษสตางค์หรือส่วนต่างเล็กน้อย อาจเกิดจากการปัดเศษหรือ adjustment ของ statement ไม่ได้แปลว่า parser ผิดทั้งไฟล์")

    if int(summary.get("material_mismatched_rows", 0) or 0) > 0:
        scenarios.append("material_balance_break")
        guidance_th.append("ยังมีแถวที่ยอดคงเหลือไม่ต่อเนื่องอย่างมีนัยสำคัญ ควรตรวจ mapping, ลำดับรายการ, และธุรกรรมช่วงที่ผิดก่อนนำผลไปใช้อ้างอิง")

    recommended_mode = "chronological" if summary.get("chronology_issue_detected") else "file_order"
    if not guidance_th:
        guidance_th.append("ไม่พบสัญญาณผิดปกติเด่นจาก balance check สามารถอ่านผลตามลำดับไฟล์ได้ตามปกติ")

    return scenarios, guidance_th, recommended_mode


def _sequence_check(transactions: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    tx = transactions.copy()

    amount_series = pd.to_numeric(tx.get("amount"), errors="coerce")
    balance_series = pd.to_numeric(tx.get("balance"), errors="coerce")
    has_statement_balance = balance_series.notna().any()

    if not has_statement_balance:
        tx["balance_source"] = "INFERRED"
        tx["expected_balance"] = balance_series.round(2)
        tx["balance_difference"] = 0.0
        tx["balance_check_status"] = "INFERRED"
        summary = {
            "status": "INFERRED",
            "balance_source": "inferred",
            "statement_balance_rows": 0,
            "matched_rows": 0,
            "mismatched_rows": 0,
            "missing_balance_rows": 0,
            "opening_reference_rows": 0,
            "unverifiable_rows": int(len(tx)),
            "max_abs_difference": 0.0,
            "opening_balance": _round_money(balance_series.iloc[0]) if len(balance_series) else None,
            "closing_balance": _round_money(balance_series.iloc[-1]) if len(balance_series) else None,
            "notes": [
                "No statement balance column was available. Running balances are inferred and cannot be independently verified."
            ],
        }
        return tx, summary

    running_reference: float | None = None
    expected_values: list[float | None] = []
    differences: list[float | None] = []
    sources: list[str] = []
    statuses: list[str] = []

    matched_rows = 0
    mismatched_rows = 0
    missing_balance_rows = 0
    opening_reference_rows = 0
    unverifiable_rows = 0
    max_abs_difference = 0.0

    for amount, balance in zip(amount_series, balance_series):
        amount_value = _round_money(amount) or 0.0
        balance_value = _round_money(balance)

        if balance_value is None:
            sources.append("MISSING")
            if running_reference is None:
                expected_values.append(None)
                differences.append(None)
                statuses.append("NO_REFERENCE")
                unverifiable_rows += 1
            else:
                running_reference = round(running_reference + amount_value, 2)
                expected_values.append(running_reference)
                differences.append(None)
                statuses.append("MISSING_STATEMENT_BALANCE")
                missing_balance_rows += 1
            continue

        sources.append("STATEMENT")
        if running_reference is None:
            expected_values.append(balance_value)
            differences.append(0.0)
            statuses.append("OPENING_REFERENCE")
            opening_reference_rows += 1
            running_reference = balance_value
            continue

        expected_balance = round(running_reference + amount_value, 2)
        difference = round(balance_value - expected_balance, 2)
        expected_values.append(expected_balance)
        differences.append(difference)

        if abs(difference) <= TOLERANCE:
            statuses.append("MATCH")
            matched_rows += 1
        else:
            statuses.append("MISMATCH")
            mismatched_rows += 1
            max_abs_difference = max(max_abs_difference, abs(difference))

        running_reference = balance_value

    tx["balance_source"] = sources
    tx["expected_balance"] = expected_values
    tx["balance_difference"] = differences
    tx["balance_check_status"] = statuses

    if mismatched_rows > 0:
        status = "FAILED"
    elif matched_rows > 0 and unverifiable_rows == 0 and missing_balance_rows == 0:
        status = "VERIFIED"
    else:
        status = "PARTIAL"

    notes: list[str] = []
    if mismatched_rows:
        notes.append("One or more statement balances do not match the sequential amount flow.")
    if missing_balance_rows:
        notes.append("Some rows have no statement balance, so those rows are carried forward but not directly verified.")
    if unverifiable_rows:
        notes.append("Some leading rows appeared before the first statement balance reference and could not be verified.")

    summary = {
        "status": status,
        "balance_source": "statement",
        "statement_balance_rows": int(balance_series.notna().sum()),
        "matched_rows": matched_rows,
        "mismatched_rows": mismatched_rows,
        "missing_balance_rows": missing_balance_rows,
        "opening_reference_rows": opening_reference_rows,
        "unverifiable_rows": unverifiable_rows,
        "max_abs_difference": round(max_abs_difference, 2),
        "opening_balance": _round_money(balance_series.dropna().iloc[0]) if balance_series.notna().any() else None,
        "closing_balance": _round_money(balance_series.dropna().iloc[-1]) if balance_series.notna().any() else None,
        "notes": notes,
    }
    return tx, summary


def reconcile_balances(transactions: pd.DataFrame) -> ReconciliationResult:
    """Annotate transaction rows with balance-reconciliation evidence."""
    tx, summary = _sequence_check(transactions)

    chronology_issue_detected = False
    chronological_mismatched_rows = summary["mismatched_rows"]
    chronological_status = summary["status"]
    chronological_max_abs_difference = summary["max_abs_difference"]
    mismatches_reduced_by_sorting = 0
    sortable_rows = 0

    sort_key = _safe_sort_timestamp(tx)
    sortable_rows = int(sort_key.notna().sum())
    missing_time_rows = int(len(tx) - sortable_rows)
    duplicate_timestamp_rows = _duplicate_timestamp_count(sort_key)
    if sortable_rows >= 2:
        sorted_tx = transactions.copy()
        sorted_tx["_recon_sort_key"] = sort_key
        stable_order = ["_recon_sort_key"]
        if "_source_row_number" in sorted_tx.columns:
            stable_order.append("_source_row_number")
        elif "row_number" in sorted_tx.columns:
            stable_order.append("row_number")
        sorted_tx = sorted_tx.sort_values(stable_order, kind="stable").drop(columns=["_recon_sort_key"])
        _, chronological_summary = _sequence_check(sorted_tx)
        chronological_mismatched_rows = int(chronological_summary["mismatched_rows"])
        chronological_status = str(chronological_summary["status"])
        chronological_max_abs_difference = float(chronological_summary["max_abs_difference"])
        if chronological_mismatched_rows < int(summary["mismatched_rows"]):
            chronology_issue_detected = True
            mismatches_reduced_by_sorting = int(summary["mismatched_rows"]) - chronological_mismatched_rows
            summary["notes"].append(
                f"Rows appear out of chronological order. Sorting by date/time reduces mismatches by {mismatches_reduced_by_sorting}."
            )

    diagnostic_mismatches = tx[tx["balance_check_status"] == "MISMATCH"].copy()
    if chronology_issue_detected and sortable_rows >= 2:
        sorted_tx = transactions.copy()
        sorted_tx["_recon_sort_key"] = _safe_sort_timestamp(transactions)
        stable_order = ["_recon_sort_key"]
        if "_source_row_number" in sorted_tx.columns:
            stable_order.append("_source_row_number")
        elif "row_number" in sorted_tx.columns:
            stable_order.append("row_number")
        sorted_tx = sorted_tx.sort_values(stable_order, kind="stable").drop(columns=["_recon_sort_key"])
        sorted_checked, _ = _sequence_check(sorted_tx)
        diagnostic_mismatches = sorted_checked[sorted_checked["balance_check_status"] == "MISMATCH"].copy()

    rounding_drift_rows = 0
    material_mismatched_rows = 0
    if not diagnostic_mismatches.empty:
        diff_series = pd.to_numeric(diagnostic_mismatches["balance_difference"], errors="coerce").abs()
        rounding_drift_rows = int((diff_series <= ROUNDING_DRIFT_TOLERANCE).sum())
        material_mismatched_rows = int((diff_series > ROUNDING_DRIFT_TOLERANCE).sum())
        if rounding_drift_rows:
            summary["notes"].append(
                f"{rounding_drift_rows} mismatch rows are small drift values (<= {ROUNDING_DRIFT_TOLERANCE:.2f}) and may reflect rounding or minor adjustments."
            )

    summary["chronology_issue_detected"] = chronology_issue_detected
    summary["sortable_rows"] = sortable_rows
    summary["missing_time_rows"] = missing_time_rows
    summary["duplicate_timestamp_rows"] = duplicate_timestamp_rows
    summary["chronological_status"] = chronological_status
    summary["chronological_mismatched_rows"] = chronological_mismatched_rows
    summary["chronological_max_abs_difference"] = round(chronological_max_abs_difference, 2)
    summary["mismatches_reduced_by_sorting"] = mismatches_reduced_by_sorting
    summary["rounding_drift_rows"] = rounding_drift_rows
    summary["material_mismatched_rows"] = material_mismatched_rows
    summary["check_modes"] = {
        "file_order": {
            "label": "File Order",
            "status": summary["status"],
            "mismatched_rows": summary["mismatched_rows"],
            "max_abs_difference": summary["max_abs_difference"],
        },
        "chronological": {
            "label": "Chronological",
            "status": chronological_status,
            "mismatched_rows": chronological_mismatched_rows,
            "max_abs_difference": round(chronological_max_abs_difference, 2),
        },
    }
    scenarios, guidance_th, recommended_mode = _build_guidance(summary, tx)
    summary["suspected_scenarios"] = scenarios
    summary["guidance_th"] = guidance_th
    summary["recommended_check_mode"] = recommended_mode

    reconciliation = _build_reconciliation_export(tx)
    return ReconciliationResult(tx, reconciliation, summary)


def _build_reconciliation_export(transactions: pd.DataFrame) -> pd.DataFrame:
    available = [column for column in RECONCILIATION_EXPORT_COLUMNS if column in transactions.columns]
    extras = [column for column in transactions.columns if column not in available]
    ordered = available + extras
    return transactions[ordered].copy().reset_index(drop=True)
