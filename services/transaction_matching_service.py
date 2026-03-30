from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from persistence.base import utcnow
from persistence.models import Account, Entity, Transaction, TransactionMatch
from utils.text_utils import normalize_text


def _name_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    left_tokens = set(normalize_text(left).lower().split())
    right_tokens = set(normalize_text(right).lower().split())
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    return intersection / union if union else 0.0


def _as_utc_comparable(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _add_match(
    session: Session,
    *,
    source_transaction_id: str,
    target_transaction_id: str | None,
    target_account_id: str | None,
    match_type: str,
    confidence_score: float,
    evidence: dict,
    status: str = "suggested",
) -> None:
    exists = session.scalars(
        select(TransactionMatch).where(
            TransactionMatch.source_transaction_id == source_transaction_id,
            TransactionMatch.target_transaction_id == target_transaction_id,
            TransactionMatch.target_account_id == target_account_id,
            TransactionMatch.match_type == match_type,
        )
    ).first()
    if exists:
        return

    row = TransactionMatch(
        source_transaction_id=source_transaction_id,
        target_transaction_id=target_transaction_id,
        target_account_id=target_account_id,
        match_type=match_type,
        confidence_score=Decimal(str(confidence_score)).quantize(Decimal("0.0001")),
        evidence_json=evidence,
        status=status,
        is_manual_confirmed=False,
        created_at=utcnow(),
    )
    session.add(row)


def generate_matches_for_transactions(session: Session, transactions: list[Transaction]) -> None:
    for transaction in transactions:
        if transaction.counterparty_account_normalized:
            account = session.scalars(
                select(Account).where(Account.normalized_account_number == transaction.counterparty_account_normalized)
            ).first()
            if account:
                _add_match(
                    session,
                    source_transaction_id=transaction.id,
                    target_transaction_id=None,
                    target_account_id=account.id,
                    match_type="exact_account_match",
                    confidence_score=1.0,
                    evidence={"counterparty_account_normalized": transaction.counterparty_account_normalized},
                )

        if transaction.reference_no:
            peer = session.scalars(
                select(Transaction).where(
                    Transaction.id != transaction.id,
                    Transaction.reference_no == transaction.reference_no,
                    Transaction.amount == (transaction.amount * Decimal("-1")),
                )
            ).first()
            if peer:
                _add_match(
                    session,
                    source_transaction_id=transaction.id,
                    target_transaction_id=peer.id,
                    target_account_id=peer.account_id,
                    match_type="reference_match",
                    confidence_score=0.80,
                    evidence={"reference_no": transaction.reference_no},
                )

        if transaction.transaction_datetime is not None:
            base_dt = _as_utc_comparable(transaction.transaction_datetime)
            peers = session.scalars(
                select(Transaction).where(
                    Transaction.id != transaction.id,
                    Transaction.amount == (transaction.amount * Decimal("-1")),
                    Transaction.transaction_datetime >= transaction.transaction_datetime - timedelta(hours=12),
                    Transaction.transaction_datetime <= transaction.transaction_datetime + timedelta(hours=12),
                )
            ).all()
            for peer in peers[:5]:
                peer_dt = _as_utc_comparable(peer.transaction_datetime)
                match_type = "probable_internal_transfer"
                confidence = 0.70
                if base_dt and peer_dt and abs((peer_dt - base_dt).total_seconds()) <= 7200:
                    match_type = "mirrored_transfer_match"
                    confidence = 0.90
                _add_match(
                    session,
                    source_transaction_id=transaction.id,
                    target_transaction_id=peer.id,
                    target_account_id=peer.account_id,
                    match_type=match_type,
                    confidence_score=confidence,
                    evidence={"amount": str(transaction.amount), "peer_transaction_id": peer.id},
                )
                break

        if transaction.counterparty_name_normalized:
            entities = session.scalars(
                select(Entity).where(
                    or_(
                        Entity.normalized_name == transaction.counterparty_name_normalized,
                        Entity.full_name == transaction.counterparty_name_normalized,
                    )
                )
            ).all()
            if not entities:
                entities = session.scalars(select(Entity).where(Entity.normalized_name.is_not(None))).all()
            best_entity = None
            best_score = 0.0
            for entity in entities[:50]:
                score = _name_similarity(transaction.counterparty_name_normalized, entity.normalized_name or entity.full_name or "")
                if score > best_score:
                    best_score = score
                    best_entity = entity
            if best_entity and best_score >= 0.92:
                _add_match(
                    session,
                    source_transaction_id=transaction.id,
                    target_transaction_id=None,
                    target_account_id=None,
                    match_type="fuzzy_name_match",
                    confidence_score=0.65,
                    evidence={"matched_entity_id": best_entity.id, "similarity": round(best_score, 3)},
                )
