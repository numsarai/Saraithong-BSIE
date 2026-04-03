"""Regression tests for deterministic mapping profile learning."""
from contextlib import contextmanager
from unittest.mock import patch

from sqlalchemy.orm import sessionmaker
from sqlmodel import Session as SQLModelSession, SQLModel, create_engine

import database
import persistence.base as base
from core.mapping_memory import find_matching_profile, save_profile


@contextmanager
def patched_db_engine(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'mapping_memory_test.db'}",
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


def test_fuzzy_profile_selection_prefers_bank_matching_profile(tmp_path):
    bank_matching_columns = ["col_a", "col_b", "col_c", "col_d"]
    competing_columns = ["col_a", "col_b", "col_e", "col_f"]
    query_columns = ["col_a", "col_b", "col_c", "col_e"]

    with patched_db_engine(tmp_path):
        bank_profile = save_profile(
            "scb",
            bank_matching_columns,
            mapping={"amount": "col_d", "description": "col_c"},
        )
        save_profile(
            "kbank",
            competing_columns,
            mapping={"amount": "col_f", "description": "col_e"},
        )

        matched = find_matching_profile(query_columns, bank="scb", threshold=0.5)

    assert matched is not None
    assert matched["profile_id"] == bank_profile["profile_id"]
    assert matched["bank"] == "scb"


def test_fuzzy_profile_selection_prefers_more_used_profile_without_bank_hint(tmp_path):
    stronger_columns = ["col_a", "col_b", "col_c", "col_d"]
    competing_columns = ["col_a", "col_b", "col_e", "col_f"]
    query_columns = ["col_a", "col_b", "col_c", "col_e"]

    with patched_db_engine(tmp_path):
        stronger_profile = save_profile(
            "scb",
            stronger_columns,
            mapping={"amount": "col_d", "description": "col_c"},
        )
        stronger_profile = save_profile(
            "scb",
            stronger_columns,
            mapping={"amount": "col_d", "description": "col_c"},
        )
        save_profile(
            "kbank",
            competing_columns,
            mapping={"amount": "col_f", "description": "col_e"},
        )

        matched = find_matching_profile(query_columns, bank="", threshold=0.5)

    assert stronger_profile["usage_count"] >= 2
    assert matched is not None
    assert matched["profile_id"] == stronger_profile["profile_id"]
    assert matched["bank"] == "scb"
