from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from database import init_db
from persistence.base import get_db_session
from persistence.models import Account, FileRecord, ParserRun, Transaction, TransactionMatch
from services.transaction_matching_service import generate_matches_for_transactions


def test_generate_matches_handles_mixed_naive_and_aware_datetimes():
    init_db()
    suffix = uuid4().hex[:8]
    left_account_number = f"12{uuid4().int % 10**8:08d}"
    right_account_number = f"98{uuid4().int % 10**8:08d}"
    file_id = f"file-{suffix}"
    run_id = f"run-{suffix}"
    left_account_id = f"acct-left-{suffix}"
    right_account_id = f"acct-right-{suffix}"
    left_tx_id = f"tx-aware-{suffix}"
    right_tx_id = f"tx-naive-{suffix}"

    with get_db_session() as session:
        session.add_all(
            [
                FileRecord(
                    id=file_id,
                    original_filename="sample.xlsx",
                    stored_path="/tmp/sample.xlsx",
                    file_hash_sha256=f"hash-{suffix}",
                    mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    file_size_bytes=128,
                    uploaded_by="tester",
                    import_status="uploaded",
                ),
                ParserRun(
                    id=run_id,
                    file_id=file_id,
                    parser_version="test",
                    mapping_profile_version="v1",
                    status="done",
                    started_at=datetime.now(timezone.utc),
                ),
                Account(
                    id=left_account_id,
                    bank_name="SCB",
                    bank_code="SCB",
                    raw_account_number=left_account_number,
                    normalized_account_number=left_account_number,
                    display_account_number=left_account_number,
                    account_holder_name="Left",
                ),
                Account(
                    id=right_account_id,
                    bank_name="SCB",
                    bank_code="SCB",
                    raw_account_number=right_account_number,
                    normalized_account_number=right_account_number,
                    display_account_number=right_account_number,
                    account_holder_name="Right",
                ),
            ]
        )
        session.commit()

        left = Transaction(
            id=left_tx_id,
            file_id=file_id,
            parser_run_id=run_id,
            account_id=left_account_id,
            amount=Decimal("-100.00"),
            currency="THB",
            direction="OUT",
            transaction_datetime=datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc),
            parse_confidence=Decimal("1.0000"),
            duplicate_status="unique",
            review_status="pending",
            linkage_status="unresolved",
        )
        right = Transaction(
            id=right_tx_id,
            file_id=file_id,
            parser_run_id=run_id,
            account_id=right_account_id,
            amount=Decimal("100.00"),
            currency="THB",
            direction="IN",
            transaction_datetime=datetime(2026, 3, 1, 10, 30, 0),
            parse_confidence=Decimal("1.0000"),
            duplicate_status="unique",
            review_status="pending",
            linkage_status="unresolved",
        )
        session.add_all([left, right])
        session.commit()

        generate_matches_for_transactions(session, [left, right])
        session.commit()

        matches = session.query(TransactionMatch).all()
        assert matches
        assert any(match.match_type == "mirrored_transfer_match" for match in matches)
