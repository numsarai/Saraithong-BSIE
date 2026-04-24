"""Case tag API regression tests."""

from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app
from persistence.base import Base
from persistence.models import Account, Alert, CaseTag, CaseTagLink, FileRecord, ParserRun, Transaction


client = TestClient(app.app)


def _make_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'case_tags.db'}")
    Base.metadata.create_all(engine)
    return engine


def _patch_session(monkeypatch, engine):
    @contextmanager
    def test_session():
        with Session(engine) as session:
            yield session

    monkeypatch.setattr("routers.case_tags.get_db_session", test_session)


def test_case_tags_endpoint_includes_link_counts(tmp_path, monkeypatch):
    engine = _make_engine(tmp_path)

    with Session(engine) as session:
        session.add(
            CaseTag(
                id="CASE-TAG-1",
                tag="CASE-ALPHA",
                description="Alpha evidence group",
                created_at=datetime(2026, 3, 31, 2, 0, tzinfo=timezone.utc),
            )
        )
        session.add_all(
            [
                CaseTagLink(id="LINK-1", case_tag_id="CASE-TAG-1", object_type="transaction", object_id="TXN-1"),
                CaseTagLink(id="LINK-2", case_tag_id="CASE-TAG-1", object_type="transaction", object_id="TXN-2"),
                CaseTagLink(id="LINK-3", case_tag_id="CASE-TAG-1", object_type="alert", object_id="ALERT-1"),
            ]
        )
        session.commit()

    _patch_session(monkeypatch, engine)

    response = client.get("/api/case-tags")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == [
        {
            "id": "CASE-TAG-1",
            "tag": "CASE-ALPHA",
            "description": "Alpha evidence group",
            "created_at": "2026-03-31T02:00:00",
            "linked_object_count": 3,
            "linked_object_counts": {"alert": 1, "transaction": 2},
        }
    ]


def test_case_tag_detail_endpoint_returns_linked_object_navigation(tmp_path, monkeypatch):
    engine = _make_engine(tmp_path)
    created_at = datetime(2026, 3, 31, 2, 0, tzinfo=timezone.utc)

    with Session(engine) as session:
        session.add(
            FileRecord(
                id="FILE-1",
                original_filename="statement.xlsx",
                stored_path="/evidence/statement.xlsx",
                file_hash_sha256="a" * 64,
                file_size_bytes=1234,
                uploaded_at=created_at,
                bank_detected="SCB",
                import_status="stored",
            )
        )
        session.add(
            ParserRun(
                id="RUN-1",
                file_id="FILE-1",
                parser_version="bsie-test",
                status="done",
                bank_detected="SCB",
                started_at=created_at,
            )
        )
        session.add(
            Account(
                id="ACCOUNT-1",
                bank_code="SCB",
                normalized_account_number="1234567890",
                display_account_number="123-456-7890",
                account_holder_name="Subject Account",
            )
        )
        session.add(
            Transaction(
                id="TXN-1",
                file_id="FILE-1",
                parser_run_id="RUN-1",
                account_id="ACCOUNT-1",
                transaction_datetime=created_at,
                amount=Decimal("-1000.00"),
                direction="OUT",
                currency="THB",
                description_raw="Transfer to suspect",
            )
        )
        session.add(
            Alert(
                id="ALERT-1",
                transaction_id="TXN-1",
                account_id="ACCOUNT-1",
                parser_run_id="RUN-1",
                rule_type="repeated_transfers",
                severity="high",
                summary="Repeated transfer pattern",
            )
        )
        session.add(
            CaseTag(
                id="CASE-TAG-1",
                tag="CASE-ALPHA",
                description="Alpha evidence group",
                created_at=created_at,
            )
        )
        session.add_all(
            [
                CaseTagLink(
                    id="LINK-TXN",
                    case_tag_id="CASE-TAG-1",
                    object_type="transaction",
                    object_id="TXN-1",
                    created_at=created_at,
                ),
                CaseTagLink(
                    id="LINK-ALERT",
                    case_tag_id="CASE-TAG-1",
                    object_type="alert",
                    object_id="ALERT-1",
                    created_at=created_at,
                ),
                CaseTagLink(
                    id="LINK-RUN",
                    case_tag_id="CASE-TAG-1",
                    object_type="parser_run",
                    object_id="RUN-1",
                    created_at=created_at,
                ),
            ]
        )
        session.commit()

    _patch_session(monkeypatch, engine)

    response = client.get("/api/case-tags/CASE-TAG-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["tag"] == "CASE-ALPHA"
    assert payload["linked_object_count"] == 3
    links = {item["object_type"]: item for item in payload["links"]}
    assert links["transaction"]["citation_id"] == "txn:TXN-1"
    assert links["transaction"]["label"] == "OUT 1,000.00 THB"
    assert links["transaction"]["summary"] == "Transfer to suspect"
    assert links["transaction"]["scope"] == {"parser_run_id": "RUN-1", "file_id": "FILE-1"}
    assert links["alert"]["citation_id"] == "alert:ALERT-1"
    assert links["alert"]["label"] == "high repeated_transfers"
    assert links["alert"]["scope"] == {"parser_run_id": "RUN-1", "account": "1234567890"}
    assert links["parser_run"]["scope"] == {"parser_run_id": "RUN-1"}
