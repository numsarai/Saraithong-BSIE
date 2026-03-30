from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from database import init_db
from persistence.base import get_db_session
from persistence.models import Account, FileRecord, ParserRun, Transaction, TransactionMatch
from services.transaction_matching_service import generate_matches_for_transactions


def test_generate_matches_handles_mixed_naive_and_aware_datetimes():
    init_db()

    with get_db_session() as session:
        session.add_all(
            [
                FileRecord(
                    id="file-1",
                    original_filename="sample.xlsx",
                    stored_path="/tmp/sample.xlsx",
                    file_hash_sha256="hash-1",
                    mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    file_size_bytes=128,
                    uploaded_by="tester",
                    import_status="uploaded",
                ),
                ParserRun(
                    id="run-1",
                    file_id="file-1",
                    parser_version="test",
                    mapping_profile_version="v1",
                    status="done",
                    started_at=datetime.now(timezone.utc),
                ),
                Account(
                    id="acct-1",
                    bank_name="SCB",
                    bank_code="SCB",
                    raw_account_number="1234567890",
                    normalized_account_number="1234567890",
                    display_account_number="1234567890",
                    account_holder_name="Left",
                ),
                Account(
                    id="acct-2",
                    bank_name="SCB",
                    bank_code="SCB",
                    raw_account_number="0987654321",
                    normalized_account_number="0987654321",
                    display_account_number="0987654321",
                    account_holder_name="Right",
                ),
            ]
        )
        session.commit()

        left = Transaction(
            id="tx-aware",
            file_id="file-1",
            parser_run_id="run-1",
            account_id="acct-1",
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
            id="tx-naive",
            file_id="file-1",
            parser_run_id="run-1",
            account_id="acct-2",
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
