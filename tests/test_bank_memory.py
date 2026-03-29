"""Regression tests for persistent bank header fingerprints."""
from contextlib import contextmanager
from unittest.mock import patch

import pandas as pd
from sqlmodel import SQLModel, create_engine

import database
from core.bank_detector import detect_bank
from core.bank_memory import find_matching_bank_fingerprint, save_bank_fingerprint


@contextmanager
def patched_db_engine(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'bank_memory_test.db'}",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    with patch.object(database, "engine", engine):
        SQLModel.metadata.create_all(engine)
        yield


def test_bank_fingerprint_round_trip(tmp_path):
    columns = ["วันที่", "เวลา", "รายการ", "ถอนเงิน", "เงินฝาก", "จำนวนเงินคงเหลือ", "ช่องทาง"]

    with patched_db_engine(tmp_path):
        saved = save_bank_fingerprint("scb", columns, header_row=1, sheet_name="รายการ")
        matched = find_matching_bank_fingerprint(columns)

    assert saved["bank_key"] == "scb"
    assert matched is not None
    assert matched["bank_key"] == "scb"
    assert matched["match_type"] == "exact_order"
    assert matched["match_score"] == 1.0


def test_detect_bank_uses_saved_fingerprint_to_break_structural_ties(tmp_path):
    columns = ["วันที่", "เวลา", "รายการ", "ถอนเงิน", "เงินฝาก", "จำนวนเงินคงเหลือ", "ช่องทาง"]
    df = pd.DataFrame(columns=columns)

    with patched_db_engine(tmp_path):
        save_bank_fingerprint("scb", columns, header_row=1, sheet_name="รายการ")
        result = detect_bank(df, extra_text="mystery_statement.xlsx")

    assert result["config_key"] == "scb"
    assert any("fingerprint:" in item for item in result["evidence"]["positive"])
