from __future__ import annotations

import json
from datetime import date, datetime, time
from pathlib import Path

import pandas as pd
from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from core.export_anx import export_anx_from_graph
from core.graph_export import write_graph_exports
from paths import EXPORTS_DIR
from persistence.base import utcnow
from persistence.models import Account, ExportJob, FileRecord, Transaction, TransactionMatch
from services.search_service import list_duplicate_groups, list_matches, search_transactions


def _ensure_dir(job_id: str) -> Path:
    target = EXPORTS_DIR / job_id
    target.mkdir(parents=True, exist_ok=True)
    return target


def _parse_date_start(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if len(text) == 10:
            return datetime.combine(date.fromisoformat(text), time.min)
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _parse_date_end(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if len(text) == 10:
            return datetime.combine(date.fromisoformat(text), time.max)
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _partial_account_from_raw(raw_value: str, normalized_value: str = "") -> str:
    if normalized_value:
        return ""
    digits = "".join(ch for ch in str(raw_value or "") if ch.isdigit())
    return digits if 1 <= len(digits) < 10 else ""


def _transaction_query(session: Session, *, limit: int = 5000, offset: int = 0, **filters) -> list[Transaction]:
    query: Select = select(Transaction).order_by(Transaction.transaction_datetime.desc(), Transaction.id.desc())
    join_account = bool(filters.get("bank"))
    if join_account:
        query = query.join(Account, Transaction.account_id == Account.id, isouter=True)

    q = str(filters.get("q", "") or "").strip()
    if q:
        like = f"%{q}%"
        query = query.where(
            or_(
                Transaction.description_normalized.like(like),
                Transaction.counterparty_name_normalized.like(like),
                Transaction.reference_no.like(like),
            )
        )

    account = str(filters.get("account", "") or "").strip()
    if account:
        query = query.where(Transaction.account_id == account)

    counterparty = str(filters.get("counterparty", "") or "").strip()
    if counterparty:
        like = f"%{counterparty}%"
        query = query.where(
            or_(
                Transaction.counterparty_account_normalized.like(like),
                Transaction.counterparty_name_normalized.like(like),
            )
        )

    amount_min = filters.get("amount_min")
    if amount_min is not None:
        query = query.where(Transaction.amount >= amount_min)

    amount_max = filters.get("amount_max")
    if amount_max is not None:
        query = query.where(Transaction.amount <= amount_max)

    date_from = _parse_date_start(str(filters.get("date_from", "") or ""))
    if date_from:
        query = query.where(
            or_(
                Transaction.transaction_datetime >= date_from,
                Transaction.posted_date >= date_from.date(),
            )
        )

    date_to = _parse_date_end(str(filters.get("date_to", "") or ""))
    if date_to:
        query = query.where(
            or_(
                Transaction.transaction_datetime <= date_to,
                Transaction.posted_date <= date_to.date(),
            )
        )

    bank = str(filters.get("bank", "") or "").strip()
    if bank:
        query = query.where(or_(Account.bank_name == bank, Account.bank_code == bank))

    reference_no = str(filters.get("reference_no", "") or "").strip()
    if reference_no:
        query = query.where(Transaction.reference_no == reference_no)

    transaction_type = str(filters.get("transaction_type", "") or "").strip()
    if transaction_type:
        query = query.where(Transaction.transaction_type == transaction_type)

    duplicate_status = str(filters.get("duplicate_status", "") or "").strip()
    if duplicate_status:
        query = query.where(Transaction.duplicate_status == duplicate_status)

    review_status = str(filters.get("review_status", "") or "").strip()
    if review_status:
        query = query.where(Transaction.review_status == review_status)

    match_status = str(filters.get("match_status", "") or "").strip()
    if match_status:
        query = query.where(Transaction.linkage_status == match_status)

    file_id = str(filters.get("file_id", "") or "").strip()
    if file_id:
        query = query.where(Transaction.file_id == file_id)

    parser_run_id = str(filters.get("parser_run_id", "") or "").strip()
    if parser_run_id:
        query = query.where(Transaction.parser_run_id == parser_run_id)

    query = query.limit(limit).offset(offset)
    return list(session.scalars(query).all())


def _build_graph_transactions_frame(session: Session, *, limit: int = 5000, **filters) -> pd.DataFrame:
    transactions = _transaction_query(session, limit=limit, **filters)
    if not transactions:
        return pd.DataFrame()

    account_ids = {tx.account_id for tx in transactions if tx.account_id}
    file_ids = {tx.file_id for tx in transactions if tx.file_id}
    account_map = {account_id: session.get(Account, account_id) for account_id in account_ids}
    file_map = {file_id: session.get(FileRecord, file_id) for file_id in file_ids}

    rows: list[dict[str, object]] = []
    for tx in transactions:
        lineage = dict(tx.lineage_json or {})
        account = account_map.get(tx.account_id)
        file_row = file_map.get(tx.file_id)
        subject_account = (account.normalized_account_number if account else "") or str(lineage.get("subject_account", "") or "")
        subject_name = (account.account_holder_name if account else "") or str(lineage.get("subject_name", "") or "")
        bank_name = (account.bank_name if account else "") or str(lineage.get("bank_detected", "") or "")
        counterparty_account = str(tx.counterparty_account_normalized or "")
        partial_account = _partial_account_from_raw(str(tx.counterparty_account_raw or ""), counterparty_account)

        if tx.direction == "IN":
            from_account = counterparty_account or (f"PARTIAL:{partial_account}" if partial_account else "UNKNOWN")
            to_account = subject_account or "UNKNOWN"
        elif tx.direction == "OUT":
            from_account = subject_account or "UNKNOWN"
            to_account = counterparty_account or (f"PARTIAL:{partial_account}" if partial_account else "UNKNOWN")
        else:
            from_account = "UNKNOWN"
            to_account = "UNKNOWN"

        tx_date = tx.posted_date.isoformat() if tx.posted_date else (tx.transaction_datetime.date().isoformat() if tx.transaction_datetime else "")
        tx_time = tx.transaction_datetime.time().strftime("%H:%M:%S") if tx.transaction_datetime else ""

        graph_lineage = {
            **lineage,
            "file_id": tx.file_id,
            "parser_run_id": tx.parser_run_id,
            "statement_batch_id": tx.statement_batch_id,
            "source_row_number": lineage.get("source_row_number", ""),
            "sheet": lineage.get("sheet", ""),
            "source_file": file_row.original_filename if file_row else lineage.get("source_file", ""),
            "source_file_path": file_row.stored_path if file_row else lineage.get("source_file_path", ""),
            "transaction_fingerprint": tx.transaction_fingerprint,
            "db_transaction_id": tx.id,
            "transaction_record_id": lineage.get("transaction_record_id", ""),
            "subject_account": subject_account,
            "subject_name": subject_name,
            "bank_detected": bank_name,
            "review_status": tx.review_status,
            "duplicate_status": tx.duplicate_status,
            "source_row_id": tx.source_row_id,
        }

        rows.append(
            {
                "db_transaction_id": tx.id,
                "transaction_id": str(lineage.get("transaction_record_id", "") or ""),
                "transaction_record_id": str(lineage.get("transaction_record_id", "") or ""),
                "transaction_fingerprint": str(tx.transaction_fingerprint or ""),
                "date": tx_date,
                "time": tx_time,
                "transaction_type": str(tx.transaction_type or ""),
                "direction": str(tx.direction or ""),
                "amount": float(tx.amount),
                "currency": str(tx.currency or "THB"),
                "balance": float(tx.balance_after) if tx.balance_after is not None else "",
                "subject_account": subject_account,
                "subject_name": subject_name,
                "counterparty_account": counterparty_account,
                "partial_account": partial_account,
                "counterparty_name": str(tx.counterparty_name_raw or tx.counterparty_name_normalized or ""),
                "from_account": from_account,
                "to_account": to_account,
                "bank": bank_name,
                "channel": str(tx.channel or ""),
                "description": str(tx.description_raw or tx.description_normalized or ""),
                "confidence": float(tx.parse_confidence),
                "review_status": str(tx.review_status or ""),
                "duplicate_status": str(tx.duplicate_status or ""),
                "statement_batch_id": str(tx.statement_batch_id or ""),
                "parser_run_id": str(tx.parser_run_id or ""),
                "file_id": str(tx.file_id or ""),
                "reference_no": str(tx.reference_no or ""),
                "row_number": str(lineage.get("source_row_number", "") or ""),
                "source_file": file_row.original_filename if file_row else str(lineage.get("source_file", "") or ""),
                "source_sheet": str(lineage.get("sheet", "") or ""),
                "source_row_id": str(tx.source_row_id or ""),
                "lineage_json": json.dumps(graph_lineage, ensure_ascii=False, sort_keys=True, default=str),
            }
        )

    return pd.DataFrame(rows)


def _build_graph_match_frame(
    session: Session,
    *,
    source_transaction_ids: set[str],
    target_account_ids: set[str],
) -> pd.DataFrame:
    if not source_transaction_ids and not target_account_ids:
        return pd.DataFrame()

    query = select(TransactionMatch)
    conditions = []
    if source_transaction_ids:
        conditions.append(TransactionMatch.source_transaction_id.in_(sorted(source_transaction_ids)))
        conditions.append(TransactionMatch.target_transaction_id.in_(sorted(source_transaction_ids)))
    if target_account_ids:
        conditions.append(TransactionMatch.target_account_id.in_(sorted(target_account_ids)))
    query = query.where(or_(*conditions))

    matches = list(session.scalars(query).all())
    if not matches:
        return pd.DataFrame()

    account_ids = {match.target_account_id for match in matches if match.target_account_id}
    account_map = {account_id: session.get(Account, account_id) for account_id in account_ids}

    rows: list[dict[str, object]] = []
    for match in matches:
        target_account = account_map.get(match.target_account_id) if match.target_account_id else None
        rows.append(
            {
                "id": match.id,
                "source_transaction_id": match.source_transaction_id,
                "target_transaction_id": match.target_transaction_id or "",
                "target_account_id": match.target_account_id or "",
                "target_account_number": target_account.normalized_account_number if target_account else "",
                "match_type": match.match_type,
                "confidence_score": float(match.confidence_score),
                "status": match.status,
                "is_manual_confirmed": bool(match.is_manual_confirmed),
                "evidence_json": match.evidence_json or {},
            }
        )

    return pd.DataFrame(rows)


def create_export_job(session: Session, *, export_type: str, filters: dict, created_by: str = "analyst") -> ExportJob:
    row = ExportJob(
        export_type=export_type,
        filters_json=filters,
        status="queued",
        created_by=created_by or "analyst",
        created_at=utcnow(),
    )
    session.add(row)
    session.flush()
    return row


def run_export_job(session: Session, job: ExportJob) -> ExportJob:
    target_dir = _ensure_dir(job.id)
    export_type = job.export_type
    filters = job.filters_json or {}

    if export_type == "transactions":
        rows = search_transactions(session, limit=5000, **filters)
        df = pd.DataFrame(rows)
        csv_path = target_dir / "transactions.csv"
        xlsx_path = target_dir / "transactions.xlsx"
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        df.to_excel(xlsx_path, index=False, engine="openpyxl")
        output_path = str(csv_path)
        summary = {"rows": len(df), "files": [csv_path.name, xlsx_path.name]}
    elif export_type == "duplicates":
        rows = list_duplicate_groups(session, limit=5000)
        df = pd.DataFrame(rows)
        csv_path = target_dir / "duplicate_review_report.csv"
        xlsx_path = target_dir / "duplicate_review_report.xlsx"
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        df.to_excel(xlsx_path, index=False, engine="openpyxl")
        output_path = str(csv_path)
        summary = {"rows": len(df), "files": [csv_path.name, xlsx_path.name]}
    elif export_type == "unresolved_matches":
        rows = list_matches(session, status="suggested", limit=5000)
        df = pd.DataFrame(rows)
        csv_path = target_dir / "unresolved_match_report.csv"
        xlsx_path = target_dir / "unresolved_match_report.xlsx"
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        df.to_excel(xlsx_path, index=False, engine="openpyxl")
        output_path = str(csv_path)
        summary = {"rows": len(df), "files": [csv_path.name, xlsx_path.name]}
    elif export_type == "corrected_transactions":
        corrected_filters = {**filters, "review_status": "reviewed"}
        rows = search_transactions(session, limit=5000, **corrected_filters)
        df = pd.DataFrame(rows)
        csv_path = target_dir / "corrected_transactions.csv"
        xlsx_path = target_dir / "corrected_transactions.xlsx"
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        df.to_excel(xlsx_path, index=False, engine="openpyxl")
        output_path = str(csv_path)
        summary = {"rows": len(df), "files": [csv_path.name, xlsx_path.name]}
    elif export_type == "graph":
        transactions_df = _build_graph_transactions_frame(session, limit=5000, **filters)
        transaction_ids = set(transactions_df["db_transaction_id"].astype(str).tolist()) if not transactions_df.empty else set()
        account_ids = set()
        if not transactions_df.empty:
            subject_accounts = {value for value in transactions_df["subject_account"].astype(str).tolist() if value}
            if subject_accounts:
                for account in session.scalars(select(Account).where(Account.normalized_account_number.in_(sorted(subject_accounts)))).all():
                    account_ids.add(account.id)
        matches_df = _build_graph_match_frame(session, source_transaction_ids=transaction_ids, target_account_ids=account_ids)
        graph_bundle = write_graph_exports(
            target_dir,
            transactions=transactions_df,
            matches=matches_df,
            batch_identity=str(filters.get("parser_run_id", "") or filters.get("file_id", "") or ""),
            batch_label="",
        )
        anx_path = target_dir / "i2_chart.anx"
        export_anx_from_graph(graph_bundle["nodes_df"], graph_bundle["edges_df"], anx_path)
        output_path = str(graph_bundle["manifest_path"])
        summary = {
            "nodes": int(graph_bundle["manifest"]["node_count"]),
            "edges": int(graph_bundle["manifest"]["edge_count"]),
            "aggregated_edges": int(graph_bundle["manifest"]["aggregated_edge_count"]),
            "files": [
                graph_bundle["nodes_path"].name,
                graph_bundle["edges_path"].name,
                graph_bundle["aggregated_edges_path"].name,
                graph_bundle["manifest_path"].name,
                anx_path.name,
            ],
        }
    else:
        payload_path = target_dir / "summary.json"
        payload_path.write_text(json.dumps({"filters": filters}, ensure_ascii=False, indent=2), encoding="utf-8")
        output_path = str(payload_path)
        summary = {"files": [payload_path.name]}

    job.status = "done"
    job.completed_at = utcnow()
    job.output_path = output_path
    job.summary_json = summary
    session.add(job)
    session.flush()
    return job
