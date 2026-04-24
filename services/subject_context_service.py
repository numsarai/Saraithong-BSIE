from __future__ import annotations

from typing import Any

from core.account_parser import parse_account


def normalize_subject_account(value: Any) -> str:
    parsed = parse_account(value)
    return str(parsed["clean"]) if parsed["type"] == "ACCOUNT" else ""


def build_subject_account_context(
    *,
    subject_account: Any = "",
    subject_name: Any = "",
    identity_guess: Any = None,
    sample_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    selected_raw = str(subject_account or "").strip()[:80]
    selected_account = normalize_subject_account(selected_raw)
    selected_name = str(subject_name or "").strip()[:160]
    guess = identity_guess if isinstance(identity_guess, dict) else {}
    inferred_account = normalize_subject_account(guess.get("account"))
    inferred_name = str(guess.get("name") or "").strip()[:160]
    account_seen_in_sample_rows = bool(selected_account and _sample_rows_contain_account(selected_account, sample_rows))

    if not selected_account:
        match_status = "no_selected_account"
    elif inferred_account and selected_account == inferred_account:
        match_status = "selected_matches_inferred"
    elif inferred_account and selected_account != inferred_account:
        match_status = "selected_conflicts_with_inferred"
    elif account_seen_in_sample_rows:
        match_status = "selected_seen_in_sample_rows"
    else:
        match_status = "selected_not_observed"

    return {
        "selected_account_raw": selected_raw,
        "selected_account": selected_account,
        "selected_name": selected_name,
        "inferred_account": inferred_account,
        "inferred_name": inferred_name,
        "account_source": str(guess.get("account_source") or "").strip()[:80],
        "name_source": str(guess.get("name_source") or "").strip()[:80],
        "account_seen_in_sample_rows": account_seen_in_sample_rows,
        "account_match_status": match_status,
        "authority": "analyst_selected" if selected_account else "not_provided",
    }


def _sample_rows_contain_account(account: str, sample_rows: list[dict[str, Any]] | None) -> bool:
    for row in sample_rows or []:
        if not isinstance(row, dict):
            continue
        for value in row.values():
            if account in "".join(ch for ch in str(value or "") if ch.isdigit()):
                return True
    return False
