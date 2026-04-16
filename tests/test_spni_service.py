"""Service-level tests for SPNI export scoping and pagination metadata."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlmodel import SQLModel

from persistence.base import Base, utcnow
from persistence.models import Account, AccountEntityLink, Entity, FileRecord, ParserRun, Transaction
from services.spni_service import export_data


def _make_engine(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'spni-service.sqlite'}", future=True)
    Base.metadata.create_all(engine)
    SQLModel.metadata.create_all(engine)
    return engine


def _make_file(file_id: str) -> FileRecord:
    return FileRecord(
        id=file_id,
        original_filename="statement.ofx",
        stored_path=f"/tmp/{file_id}.ofx",
        storage_key=f"{file_id}/original.ofx",
        file_hash_sha256=(file_id.replace("-", "") * 2)[:64].ljust(64, "0"),
        mime_type="application/x-ofx",
        file_size_bytes=128,
        uploaded_at=utcnow(),
        uploaded_by="tester",
        import_status="uploaded",
    )


def _make_run(run_id: str, file_id: str) -> ParserRun:
    return ParserRun(
        id=run_id,
        file_id=file_id,
        parser_version="4.0.0",
        started_at=utcnow(),
        finished_at=utcnow(),
        status="done",
        bank_detected="scb",
        warning_count=0,
        error_count=0,
        summary_json={},
    )


def _make_account(account_id: str, normalized: str, holder: str) -> Account:
    return Account(
        id=account_id,
        bank_code="scb",
        bank_name="SCB",
        normalized_account_number=normalized,
        account_holder_name=holder,
        account_type="savings",
        first_seen_at=utcnow(),
        last_seen_at=utcnow(),
        confidence_score=Decimal("1.0000"),
        source_count=1,
        status="active",
    )


def _make_transaction(
    tx_id: str,
    file_id: str,
    run_id: str,
    account_id: str,
    amount: str,
    *,
    when: datetime,
) -> Transaction:
    return Transaction(
        id=tx_id,
        file_id=file_id,
        parser_run_id=run_id,
        account_id=account_id,
        transaction_datetime=when,
        amount=Decimal(amount),
        currency="THB",
        direction="OUT",
        description_raw=f"raw-{tx_id}",
        description_normalized=f"normalized-{tx_id}",
        counterparty_account_normalized=f"cp-{tx_id}",
        counterparty_name_normalized=f"Counterparty {tx_id}",
        parse_confidence=Decimal("0.9500"),
        duplicate_status="unique",
        review_status="pending",
        linkage_status="unresolved",
    )


def test_export_data_keeps_account_and_entity_metadata_consistent_under_pagination(tmp_path: Path):
    engine = _make_engine(tmp_path)
    file_row = _make_file("66666666-6666-6666-6666-666666666666")
    run = _make_run("run-001", file_row.id)
    account_one = _make_account("acct-001", "1111111111", "Account One")
    account_two = _make_account("acct-002", "2222222222", "Account Two")

    entity_one = Entity(
        id="ent-001",
        entity_type="PERSON",
        full_name="Entity One",
        normalized_name="entity one",
        alias_json=[],
        identifier_value="111",
        created_at=utcnow(),
    )
    entity_two = Entity(
        id="ent-002",
        entity_type="PERSON",
        full_name="Entity Two",
        normalized_name="entity two",
        alias_json=[],
        identifier_value="222",
        created_at=utcnow(),
    )

    link_one = AccountEntityLink(
        id="link-001",
        account_id=account_one.id,
        entity_id=entity_one.id,
        link_type="owner",
        confidence_score=Decimal("1.0000"),
        is_manual_confirmed=False,
        created_at=utcnow(),
    )
    link_two = AccountEntityLink(
        id="link-002",
        account_id=account_two.id,
        entity_id=entity_two.id,
        link_type="owner",
        confidence_score=Decimal("1.0000"),
        is_manual_confirmed=False,
        created_at=utcnow(),
    )

    tx_one = _make_transaction(
        "tx-001",
        file_row.id,
        run.id,
        account_one.id,
        "100.00",
        when=datetime(2024, 5, 1, 9, 0, tzinfo=timezone.utc),
    )
    tx_two = _make_transaction(
        "tx-002",
        file_row.id,
        run.id,
        account_two.id,
        "200.00",
        when=datetime(2024, 5, 2, 9, 0, tzinfo=timezone.utc),
    )

    with Session(engine) as session:
        session.add_all([
            file_row,
            run,
            account_one,
            account_two,
            entity_one,
            entity_two,
            link_one,
            link_two,
            tx_one,
            tx_two,
        ])
        session.commit()

        result = export_data(session, run_id=run.id, limit=1, offset=0)

    assert result["meta"]["total_transactions"] == 2
    assert result["meta"]["total_accounts"] == 2
    assert result["meta"]["total_entities"] == 2
    assert len(result["transactions"]) == 1
    assert {row["id"] for row in result["accounts"]} == {account_one.id, account_two.id}
    assert {row["id"] for row in result["entities"]} == {entity_one.id, entity_two.id}
