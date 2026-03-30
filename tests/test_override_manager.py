from unittest.mock import patch

import pandas as pd

from core.override_manager import apply_overrides_to_df


def test_apply_overrides_ignores_unscoped_legacy_override_for_account_scoped_run():
    df = pd.DataFrame([
        {
            "transaction_id": "TXN-000001",
            "from_account": "OLD_FROM",
            "to_account": "OLD_TO",
            "confidence": 0.5,
        }
    ])

    with patch("core.override_manager.get_all_overrides", return_value=[
        {
            "transaction_id": "TXN-000001",
            "account_number": "",
            "override_from_account": "ACC_A",
            "override_to_account": "ACC_B",
            "override_reason": "legacy test",
            "override_by": "analyst",
            "override_timestamp": "2026-03-19T20:49:46.816871",
        }
    ]):
        result = apply_overrides_to_df(df, account_number="7882476275")

    assert str(result.loc[0, "is_overridden"]).lower() in {"false", "0"}
    assert result.loc[0, "from_account"] == "OLD_FROM"
    assert result.loc[0, "to_account"] == "OLD_TO"


def test_apply_overrides_applies_only_matching_account_scope():
    df = pd.DataFrame([
        {
            "transaction_id": "TXN-000001",
            "from_account": "OLD_FROM",
            "to_account": "OLD_TO",
            "confidence": 0.5,
        }
    ])

    with patch("core.override_manager.get_all_overrides", return_value=[
        {
            "transaction_id": "TXN-000001",
            "account_number": "7882476275",
            "override_from_account": "ACC_A",
            "override_to_account": "ACC_B",
            "override_reason": "scoped",
            "override_by": "analyst",
            "override_timestamp": "2026-03-19T20:49:46.816871",
        },
        {
            "transaction_id": "TXN-000001",
            "account_number": "9999999999",
            "override_from_account": "WRONG_A",
            "override_to_account": "WRONG_B",
            "override_reason": "other account",
            "override_by": "analyst",
            "override_timestamp": "2026-03-19T20:49:46.816871",
        },
    ]):
        result = apply_overrides_to_df(df, account_number="7882476275")

    assert bool(result.loc[0, "is_overridden"]) is True
    assert result.loc[0, "from_account"] == "ACC_A"
    assert result.loc[0, "to_account"] == "ACC_B"
