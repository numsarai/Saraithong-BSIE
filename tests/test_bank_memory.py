"""Regression tests for persistent bank header fingerprints."""
from contextlib import contextmanager
from unittest.mock import patch

import pandas as pd
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session as SQLModelSession, SQLModel, create_engine

import database
import persistence.base as base
from core.bank_detector import detect_bank
from core.bank_memory import find_matching_bank_fingerprint, save_bank_fingerprint


@contextmanager
def patched_db_engine(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'bank_memory_test.db'}",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    legacy_session_factory = sessionmaker(
        bind=engine,
        class_=SQLModelSession,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    with (
        patch.object(database, "engine", engine),
        patch.object(base, "engine", engine),
        patch.object(base, "LegacySessionLocal", legacy_session_factory),
        patch.object(base, "SessionLocal", legacy_session_factory),
    ):
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


def test_bank_fingerprint_prefers_stronger_prior_candidate_when_overlap_ties(tmp_path):
    base_columns = ["col_a", "col_b", "col_c", "col_d"]
    stronger_columns = ["col_a", "col_b", "col_e", "col_f"]
    query_columns = ["col_a", "col_b", "col_c", "col_e"]

    with patched_db_engine(tmp_path):
        stronger = save_bank_fingerprint("bank_strong", base_columns, header_row=1, sheet_name="Sheet1")
        stronger = save_bank_fingerprint("bank_strong", base_columns, header_row=1, sheet_name="Sheet1")
        save_bank_fingerprint("bank_weaker", stronger_columns, header_row=1, sheet_name="Sheet1")

        matched = find_matching_bank_fingerprint(query_columns, threshold=0.5)

    assert stronger["usage_count"] >= 2
    assert matched is not None
    assert matched["bank_key"] == "bank_strong"
    assert matched["match_type"] == "jaccard"
