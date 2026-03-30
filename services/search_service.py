from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from persistence.models import (
    Account,
    AuditLog,
    DuplicateGroup,
    ExportJob,
    FileRecord,
    ParserRun,
    Transaction,
    TransactionMatch,
)


def _apply_limit_offset(query: Select, limit: int = 100, offset: int = 0) -> Select:
    return query.limit(limit).offset(offset)


def list_files(session: Session, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    rows = session.scalars(_apply_limit_offset(select(FileRecord).order_by(FileRecord.uploaded_at.desc()), limit, offset)).all()
    return [
        {
            "id": row.id,
            "original_filename": row.original_filename,
            "file_hash_sha256": row.file_hash_sha256,
            "uploaded_at": row.uploaded_at.isoformat() if row.uploaded_at else None,
            "uploaded_by": row.uploaded_by,
            "bank_detected": row.bank_detected,
            "import_status": row.import_status,
            "stored_path": row.stored_path,
        }
        for row in rows
    ]


def get_file_detail(session: Session, file_id: str) -> dict[str, Any] | None:
    row = session.get(FileRecord, file_id)
    if not row:
        return None
    runs = session.scalars(select(ParserRun).where(ParserRun.file_id == file_id).order_by(ParserRun.started_at.desc())).all()
    return {
        "id": row.id,
        "original_filename": row.original_filename,
        "file_hash_sha256": row.file_hash_sha256,
        "uploaded_at": row.uploaded_at.isoformat() if row.uploaded_at else None,
        "uploaded_by": row.uploaded_by,
        "bank_detected": row.bank_detected,
        "import_status": row.import_status,
        "stored_path": row.stored_path,
        "parser_runs": [
            {
                "id": run.id,
                "status": run.status,
                "bank_detected": run.bank_detected,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                "summary_json": run.summary_json or {},
            }
            for run in runs
        ],
    }


def list_parser_runs(session: Session, limit: int = 100, offset: int = 0, file_id: str | None = None) -> list[dict]:
    query = select(ParserRun).order_by(ParserRun.started_at.desc())
    if file_id:
        query = query.where(ParserRun.file_id == file_id)
    rows = session.scalars(_apply_limit_offset(query, limit, offset)).all()
    return [
        {
            "id": row.id,
            "file_id": row.file_id,
            "status": row.status,
            "bank_detected": row.bank_detected,
            "parser_version": row.parser_version,
            "mapping_profile_version": row.mapping_profile_version,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            "summary_json": row.summary_json or {},
        }
        for row in rows
    ]


def list_accounts(session: Session, q: str = "", limit: int = 100, offset: int = 0) -> list[dict]:
    query = select(Account).order_by(Account.last_seen_at.desc())
    if q:
        like = f"%{q}%"
        query = query.where(
            or_(
                Account.normalized_account_number.like(like),
                Account.account_holder_name.like(like),
                Account.bank_name.like(like),
            )
        )
    rows = session.scalars(_apply_limit_offset(query, limit, offset)).all()
    return [
        {
            "id": row.id,
            "bank_name": row.bank_name,
            "normalized_account_number": row.normalized_account_number,
            "account_holder_name": row.account_holder_name,
            "status": row.status,
            "first_seen_at": row.first_seen_at.isoformat() if row.first_seen_at else None,
            "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
            "source_count": row.source_count,
        }
        for row in rows
    ]


def get_account_detail(session: Session, account_id: str) -> dict | None:
    row = session.get(Account, account_id)
    if not row:
        return None
    transactions = session.scalars(
        select(Transaction).where(Transaction.account_id == account_id).order_by(Transaction.transaction_datetime.desc()).limit(25)
    ).all()
    return {
        "id": row.id,
        "bank_name": row.bank_name,
        "normalized_account_number": row.normalized_account_number,
        "account_holder_name": row.account_holder_name,
        "status": row.status,
        "notes": row.notes,
        "transactions": [serialize_transaction(tx) for tx in transactions],
    }


def serialize_transaction(row: Transaction) -> dict:
    return {
        "id": row.id,
        "account_id": row.account_id,
        "statement_batch_id": row.statement_batch_id,
        "file_id": row.file_id,
        "parser_run_id": row.parser_run_id,
        "transaction_datetime": row.transaction_datetime.isoformat() if row.transaction_datetime else None,
        "amount": float(row.amount),
        "direction": row.direction,
        "balance_after": float(row.balance_after) if row.balance_after is not None else None,
        "description_normalized": row.description_normalized,
        "reference_no": row.reference_no,
        "channel": row.channel,
        "transaction_type": row.transaction_type,
        "counterparty_account_normalized": row.counterparty_account_normalized,
        "counterparty_name_normalized": row.counterparty_name_normalized,
        "duplicate_status": row.duplicate_status,
        "duplicate_group_id": row.duplicate_group_id,
        "review_status": row.review_status,
        "linkage_status": row.linkage_status,
        "lineage_json": row.lineage_json or {},
    }


def search_transactions(
    session: Session,
    *,
    q: str = "",
    account: str = "",
    counterparty: str = "",
    amount_min: float | None = None,
    amount_max: float | None = None,
    date_from: str = "",
    date_to: str = "",
    bank: str = "",
    reference_no: str = "",
    transaction_type: str = "",
    duplicate_status: str = "",
    review_status: str = "",
    match_status: str = "",
    file_id: str = "",
    parser_run_id: str = "",
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    query = select(Transaction).order_by(Transaction.transaction_datetime.desc())
    if bank or account:
        query = query.join(Account, Transaction.account_id == Account.id, isouter=True)
    if q:
        like = f"%{q}%"
        query = query.where(
            or_(
                Transaction.description_normalized.like(like),
                Transaction.counterparty_name_normalized.like(like),
                Transaction.reference_no.like(like),
            )
        )
    if account:
        account_like = f"%{account}%"
        query = query.where(
            or_(
                Transaction.account_id == account,
                Account.normalized_account_number == account,
                Account.display_account_number == account,
                Account.raw_account_number == account,
                Account.normalized_account_number.like(account_like),
                Account.display_account_number.like(account_like),
                Account.raw_account_number.like(account_like),
            )
        )
    if counterparty:
        like = f"%{counterparty}%"
        query = query.where(
            or_(
                Transaction.counterparty_account_normalized.like(like),
                Transaction.counterparty_name_normalized.like(like),
            )
        )
    if amount_min is not None:
        query = query.where(Transaction.amount >= amount_min)
    if amount_max is not None:
        query = query.where(Transaction.amount <= amount_max)
    if date_from:
        try:
            start_dt = datetime.combine(date.fromisoformat(date_from[:10]), time.min)
            query = query.where(
                or_(
                    Transaction.transaction_datetime >= start_dt,
                    Transaction.posted_date >= start_dt.date(),
                )
            )
        except ValueError:
            pass
    if date_to:
        try:
            end_dt = datetime.combine(date.fromisoformat(date_to[:10]), time.max)
            query = query.where(
                or_(
                    Transaction.transaction_datetime <= end_dt,
                    Transaction.posted_date <= end_dt.date(),
                )
            )
        except ValueError:
            pass
    if bank:
        query = query.where(or_(Account.bank_name == bank, Account.bank_code == bank))
    if reference_no:
        query = query.where(Transaction.reference_no == reference_no)
    if transaction_type:
        query = query.where(Transaction.transaction_type == transaction_type)
    if duplicate_status:
        query = query.where(Transaction.duplicate_status == duplicate_status)
    if review_status:
        query = query.where(Transaction.review_status == review_status)
    if match_status:
        query = query.where(Transaction.linkage_status == match_status)
    if file_id:
        query = query.where(Transaction.file_id == file_id)
    if parser_run_id:
        query = query.where(Transaction.parser_run_id == parser_run_id)
    rows = session.scalars(_apply_limit_offset(query, limit, offset)).all()
    return [serialize_transaction(row) for row in rows]


def list_duplicate_groups(session: Session, limit: int = 100, offset: int = 0) -> list[dict]:
    rows = session.scalars(_apply_limit_offset(select(DuplicateGroup).order_by(DuplicateGroup.created_at.desc()), limit, offset)).all()
    return [
        {
            "id": row.id,
            "duplicate_type": row.duplicate_type,
            "confidence_score": float(row.confidence_score),
            "reason": row.reason,
            "resolution_status": row.resolution_status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


def list_matches(session: Session, status: str = "", limit: int = 100, offset: int = 0) -> list[dict]:
    query = select(TransactionMatch).order_by(TransactionMatch.created_at.desc())
    if status:
        query = query.where(TransactionMatch.status == status)
    rows = session.scalars(_apply_limit_offset(query, limit, offset)).all()
    return [
        {
            "id": row.id,
            "source_transaction_id": row.source_transaction_id,
            "target_transaction_id": row.target_transaction_id,
            "target_account_id": row.target_account_id,
            "match_type": row.match_type,
            "confidence_score": float(row.confidence_score),
            "status": row.status,
            "is_manual_confirmed": row.is_manual_confirmed,
            "evidence_json": row.evidence_json or {},
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


def list_audit_logs(session: Session, object_type: str = "", object_id: str = "", limit: int = 200, offset: int = 0) -> list[dict]:
    query = select(AuditLog).order_by(AuditLog.changed_at.desc())
    if object_type:
        query = query.where(AuditLog.object_type == object_type)
    if object_id:
        query = query.where(AuditLog.object_id == object_id)
    rows = session.scalars(_apply_limit_offset(query, limit, offset)).all()
    return [
        {
            "id": row.id,
            "object_type": row.object_type,
            "object_id": row.object_id,
            "action_type": row.action_type,
            "field_name": row.field_name,
            "old_value_json": row.old_value_json,
            "new_value_json": row.new_value_json,
            "changed_by": row.changed_by,
            "changed_at": row.changed_at.isoformat() if row.changed_at else None,
            "reason": row.reason,
            "extra_context_json": row.extra_context_json or {},
        }
        for row in rows
    ]


def list_export_jobs(session: Session, limit: int = 100, offset: int = 0) -> list[dict]:
    rows = session.scalars(_apply_limit_offset(select(ExportJob).order_by(ExportJob.created_at.desc()), limit, offset)).all()
    return [
        {
            "id": row.id,
            "export_type": row.export_type,
            "status": row.status,
            "created_by": row.created_by,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "output_path": row.output_path,
            "summary_json": row.summary_json or {},
        }
        for row in rows
    ]
