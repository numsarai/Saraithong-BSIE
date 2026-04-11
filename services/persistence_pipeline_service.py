from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select

from persistence.base import get_db_session, utcnow
from persistence.models import (
    AccountEntityLink,
    Entity,
    FileRecord,
    MappingProfileRecord,
    ParserRun,
    RawImportRow,
    StatementBatch,
    Transaction,
)
from services.account_resolution_service import bank_code_from_name, normalize_account_number, resolve_account
from services.duplicate_detection_service import classify_transaction_duplicate, detect_batch_overlap
from services.export_service import create_export_job
from services.fingerprinting import batch_fingerprint, decimal_or_none, mapping_profile_version, parse_datetime, transaction_fingerprint
from services.transaction_matching_service import generate_matches_for_transactions
from utils.text_utils import normalize_text


PARSER_VERSION = "3.0.0"


def _upsert_account_entity_link(
    session,
    *,
    account_id: str,
    entity_id: str,
    link_type: str,
    confidence_score: Decimal = Decimal("1.0000"),
    source_reason: str = "",
) -> None:
    """Insert an AccountEntityLink only if the (account, entity, type) combo doesn't exist."""
    existing = session.scalars(
        select(AccountEntityLink).where(
            AccountEntityLink.account_id == account_id,
            AccountEntityLink.entity_id == entity_id,
            AccountEntityLink.link_type == link_type,
        )
    ).first()
    if existing:
        return
    session.add(AccountEntityLink(
        account_id=account_id,
        entity_id=entity_id,
        link_type=link_type,
        confidence_score=confidence_score,
        source_reason=source_reason,
        is_manual_confirmed=False,
        created_at=utcnow(),
    ))


def _to_python_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _row_to_json(row: pd.Series) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in row.to_dict().items():
        if pd.isna(value):
            payload[str(key)] = None
        else:
            payload[str(key)] = str(value)
    return payload


def _legacy_account_package_files(output_dir: Path) -> list[str]:
    files = ["meta.json"]
    processed_dir = output_dir / "processed"
    if not processed_dir.exists():
        return files
    files.extend(
        f"processed/{path.name}"
        for path in sorted(processed_dir.iterdir(), key=lambda item: item.name.lower())
        if path.is_file()
    )
    return files


def _sync_mapping_profile(session, *, bank_key: str, confirmed_mapping: dict | None) -> tuple[str | None, str | None]:
    if not confirmed_mapping:
        return None, None

    version = mapping_profile_version(confirmed_mapping)
    existing = session.scalars(
        select(MappingProfileRecord).where(
            MappingProfileRecord.bank_name == (bank_key or "UNKNOWN"),
            MappingProfileRecord.profile_version == version,
        )
    ).first()
    if existing:
        return existing.id, existing.profile_version

    row = MappingProfileRecord(
        bank_name=bank_key or "UNKNOWN",
        profile_name=f"{(bank_key or 'generic').upper()} confirmed mapping",
        profile_version=version,
        column_mapping_json=confirmed_mapping,
        transformation_rules_json={},
        columns_signature=None,
        created_at=utcnow(),
        updated_at=utcnow(),
        is_active=True,
    )
    session.add(row)
    session.flush()
    return row.id, row.profile_version


def create_parser_run(
    *,
    file_id: str,
    bank_detected: str = "",
    confirmed_mapping: dict | None = None,
    operator: str = "analyst",
) -> dict[str, str]:
    with get_db_session() as session:
        mapping_profile_id, mapping_version = _sync_mapping_profile(
            session,
            bank_key=bank_detected,
            confirmed_mapping=confirmed_mapping,
        )
        row = ParserRun(
            file_id=file_id,
            parser_version=PARSER_VERSION,
            mapping_profile_version=mapping_version,
            mapping_profile_id=mapping_profile_id,
            started_at=utcnow(),
            status="queued",
            bank_detected=bank_detected or None,
            warning_count=0,
            error_count=0,
            summary_json={"operator": operator or "analyst"},
        )
        session.add(row)
        file_row = session.get(FileRecord, file_id)
        if file_row:
            file_row.bank_detected = bank_detected or file_row.bank_detected
            file_row.parser_version = PARSER_VERSION
            file_row.mapping_profile_id = mapping_profile_id
            file_row.import_status = "queued"
            session.add(file_row)
        session.commit()
        return {
            "parser_run_id": row.id,
            "mapping_profile_id": mapping_profile_id or "",
            "mapping_profile_version": mapping_version or "",
        }


def mark_parser_run_failed(parser_run_id: str, error: str) -> None:
    with get_db_session() as session:
        parser_run = session.get(ParserRun, parser_run_id)
        if not parser_run:
            return
        parser_run.status = "error"
        parser_run.finished_at = utcnow()
        parser_run.error_count = int(parser_run.error_count or 0) + 1
        parser_run.summary_json = {**(parser_run.summary_json or {}), "error": error}
        session.add(parser_run)
        file_row = session.get(FileRecord, parser_run.file_id)
        if file_row:
            file_row.import_status = "error"
            session.add(file_row)
        session.commit()


def _cleanup_prior_runs(session, file_id: str, current_parser_run_id: str) -> int:
    """Delete data from prior parser runs for the same file, excluding the current run.

    This prevents duplicate transactions from accumulating when re-processing.
    """
    from persistence.models import Alert, TransactionMatch

    prior_runs = session.scalars(
        select(ParserRun).where(
            ParserRun.file_id == file_id,
            ParserRun.id != current_parser_run_id,
            ParserRun.status == "done",
        )
    ).all()

    if not prior_runs:
        return 0

    prior_run_ids = [r.id for r in prior_runs]
    deleted_count = 0

    for run_id in prior_run_ids:
        # Delete transaction matches for transactions in this run
        txn_ids = [t.id for t in session.scalars(
            select(Transaction).where(Transaction.parser_run_id == run_id)
        ).all()]

        if txn_ids:
            session.execute(
                TransactionMatch.__table__.delete().where(
                    TransactionMatch.source_transaction_id.in_(txn_ids)
                )
            )
            session.execute(
                TransactionMatch.__table__.delete().where(
                    TransactionMatch.target_transaction_id.in_(txn_ids)
                )
            )
            # Delete alerts for these transactions
            session.execute(
                Alert.__table__.delete().where(Alert.parser_run_id == run_id)
            )

        # Delete transactions
        deleted = session.execute(
            Transaction.__table__.delete().where(Transaction.parser_run_id == run_id)
        ).rowcount
        deleted_count += deleted

        # Delete raw import rows
        session.execute(
            RawImportRow.__table__.delete().where(RawImportRow.parser_run_id == run_id)
        )

        # Delete statement batches
        session.execute(
            StatementBatch.__table__.delete().where(StatementBatch.parser_run_id == run_id)
        )

        # Mark the old parser run as superseded
        for run in prior_runs:
            if run.id == run_id:
                run.status = "superseded"
                session.add(run)

    if deleted_count:
        import logging
        logging.getLogger(__name__).info(
            "Cleaned %d transactions from %d prior parser runs for file %s",
            deleted_count, len(prior_run_ids), file_id,
        )

    return deleted_count


def persist_pipeline_run(
    *,
    file_id: str,
    parser_run_id: str,
    source_file: str | Path,
    raw_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    entities_df: pd.DataFrame,
    bank_key: str,
    bank_name: str,
    subject_account: str,
    subject_name: str,
    confirmed_mapping: dict | None,
    header_row: int,
    sheet_name: str,
    output_dir: Path,
    operator: str = "analyst",
) -> None:
    source_file = Path(source_file)
    with get_db_session() as session:
        parser_run = session.get(ParserRun, parser_run_id)
        if not parser_run:
            raise ValueError(f"Parser run {parser_run_id} not found")
        file_row = session.get(FileRecord, file_id)
        if not file_row:
            raise ValueError(f"File {file_id} not found")

        # Clean up data from prior parser runs for this file to prevent duplicates
        _cleanup_prior_runs(session, file_id, parser_run_id)

        mapping_profile_id, mapping_version = _sync_mapping_profile(session, bank_key=bank_key, confirmed_mapping=confirmed_mapping)
        parser_run.mapping_profile_id = mapping_profile_id
        parser_run.mapping_profile_version = mapping_version
        parser_run.bank_detected = bank_key or parser_run.bank_detected

        subject_account_row = resolve_account(
            session,
            bank_name=bank_name,
            raw_account_number=subject_account,
            account_holder_name=subject_name,
            notes="subject account from parser run",
        )
        effective_subject_name = str(
            (subject_account_row.account_holder_name if subject_account_row else "") or subject_name or ""
        ).strip()

        raw_row_map: dict[int, str] = {}
        raw_rows_to_insert: list[RawImportRow] = []
        raw_row_numbers: list[int] = []
        for row in raw_df.reset_index(drop=True).itertuples(index=True):
            idx = row.Index
            source_row_number = int(getattr(row, "_source_row_number", 0) or (header_row + idx + 2))
            payload = {str(k): (None if pd.isna(v) else str(v)) for k, v in row._asdict().items() if k != "Index"}
            raw_row_obj = RawImportRow(
                file_id=file_id,
                parser_run_id=parser_run_id,
                sheet_name=sheet_name,
                source_row_number=source_row_number,
                raw_row_json=payload,
                parsed_status="parsed",
                warning_json=[],
            )
            raw_rows_to_insert.append(raw_row_obj)
            raw_row_numbers.append(source_row_number)
        session.add_all(raw_rows_to_insert)
        session.flush()  # single flush for all raw rows
        for raw_row_obj, src_num in zip(raw_rows_to_insert, raw_row_numbers):
            raw_row_map[src_num] = raw_row_obj.id

        tx_df = transactions_df.copy()
        tx_df["date"] = tx_df.get("date", "").fillna("")
        tx_df["amount"] = tx_df.get("amount", 0).fillna(0)
        dates = [d for d in tx_df["date"].tolist() if str(d).strip()]
        opening_balance = decimal_or_none(tx_df.iloc[0].get("balance")) if not tx_df.empty else None
        closing_balance = decimal_or_none(tx_df.iloc[-1].get("balance")) if not tx_df.empty else None
        debit_total = sum(abs(float(v)) for v in tx_df["amount"].tolist() if float(v) < 0) if not tx_df.empty else 0.0
        credit_total = sum(float(v) for v in tx_df["amount"].tolist() if float(v) > 0) if not tx_df.empty else 0.0
        batch_payload = {
            "account_number": subject_account,
            "statement_start_date": min(dates) if dates else "",
            "statement_end_date": max(dates) if dates else "",
            "transaction_count": len(tx_df),
            "opening_balance": opening_balance,
            "closing_balance": closing_balance,
            "debit_total": debit_total,
            "credit_total": credit_total,
        }
        batch_fp = batch_fingerprint(batch_payload)
        overlap_status = detect_batch_overlap(
            session,
            account_id=subject_account_row.id if subject_account_row else None,
            fingerprint=batch_fp,
            start_date=_to_python_date(batch_payload["statement_start_date"]),
            end_date=_to_python_date(batch_payload["statement_end_date"]),
        )
        batch = StatementBatch(
            file_id=file_id,
            parser_run_id=parser_run_id,
            account_id=subject_account_row.id if subject_account_row else None,
            statement_start_date=_to_python_date(batch_payload["statement_start_date"]),
            statement_end_date=_to_python_date(batch_payload["statement_end_date"]),
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            debit_total=Decimal(str(debit_total)).quantize(Decimal("0.01")),
            credit_total=Decimal(str(credit_total)).quantize(Decimal("0.01")),
            transaction_count=len(tx_df),
            batch_fingerprint=batch_fp,
            overlap_status=overlap_status,
            created_at=utcnow(),
        )
        session.add(batch)
        session.flush()

        entity_lookup: dict[tuple[str, str], str] = {}
        # Prefetch all existing entities in one query
        existing_entities = session.scalars(select(Entity)).all()
        for ent in existing_entities:
            entity_lookup[(ent.entity_type, ent.identifier_value)] = ent.id

        new_entities: list[Entity] = []
        for row in entities_df.fillna("").itertuples(index=False):
            entity_type = str(getattr(row, "entity_type", "UNKNOWN") or "UNKNOWN")
            identifier_value = str(getattr(row, "account_number", "") or getattr(row, "name", "") or "UNKNOWN")
            if (entity_type, identifier_value) in entity_lookup:
                continue
            normalized_name = normalize_text(getattr(row, "name", "") or "").lower() or None
            entity = Entity(
                entity_type=entity_type,
                full_name=str(getattr(row, "name", "") or "") or None,
                normalized_name=normalized_name,
                alias_json=[],
                identifier_value=identifier_value,
                notes=None,
                created_at=utcnow(),
            )
            new_entities.append(entity)
            entity_lookup[(entity_type, identifier_value)] = None  # placeholder
        if new_entities:
            session.add_all(new_entities)
            session.flush()  # single flush for all new entities
            for entity in new_entities:
                entity_lookup[(entity.entity_type, entity.identifier_value)] = entity.id

        if subject_account_row:
            subject_entity_id = entity_lookup.get(("ACCOUNT", subject_account_row.normalized_account_number or ""))
            if subject_entity_id:
                _upsert_account_entity_link(
                    session,
                    account_id=subject_account_row.id,
                    entity_id=subject_entity_id,
                    link_type="owns",
                    confidence_score=Decimal("1.0000"),
                    source_reason="subject account entity",
                )

        persisted_transactions: list[Transaction] = []
        pending_cp_links: list[tuple] = []  # (cp_account_number, cp_name) for batch resolve
        BATCH_SIZE = 200

        for row in tx_df.fillna("").itertuples(index=False):
            row_dict = row._asdict()
            tx_payload = {
                "account_id": subject_account_row.id if subject_account_row else None,
                "parser_run_id": parser_run_id,
                "transaction_datetime": parse_datetime(row_dict.get("date"), row_dict.get("time")),
                "amount": decimal_or_none(row_dict.get("amount")) or Decimal("0.00"),
                "direction": str(row_dict.get("direction", "") or "UNKNOWN"),
                "description_normalized": normalize_text(row_dict.get("description", "") or "").lower(),
                "reference_no": str(row_dict.get("reference_no", "") or "").strip() or None,
                "counterparty_account_normalized": normalize_account_number(row_dict.get("counterparty_account")),
                "balance_after": decimal_or_none(row_dict.get("balance")),
                "transaction_type": str(row_dict.get("transaction_type", "") or "").strip() or None,
            }
            tx_payload["transaction_fingerprint"] = transaction_fingerprint(tx_payload)
            duplicate_status, duplicate_group_id, duplicate_confidence, duplicate_reason = classify_transaction_duplicate(session, tx_payload)
            source_row_number = int(row_dict.get("_source_row_number") or row_dict.get("row_number") or 0)
            lineage = {
                "file_id": file_id,
                "parser_run_id": parser_run_id,
                "sheet": sheet_name,
                "source_row_number": source_row_number,
                "raw_source_snapshot": raw_row_map.get(source_row_number),
                "source_file": source_file.name,
                "source_file_path": str(source_file),
                "parser_version": PARSER_VERSION,
                "mapping_profile_version": mapping_version,
                "manual_corrections_applied": [],
                "bank_detected": bank_key,
                "duplicate_reason": duplicate_reason,
                "transaction_record_id": str(row_dict.get("transaction_id", "") or ""),
                "subject_account": subject_account,
                "subject_name": effective_subject_name,
            }
            transaction = Transaction(
                statement_batch_id=batch.id,
                file_id=file_id,
                parser_run_id=parser_run_id,
                source_row_id=raw_row_map.get(source_row_number),
                account_id=subject_account_row.id if subject_account_row else None,
                transaction_datetime=tx_payload["transaction_datetime"],
                posted_date=_to_python_date(row_dict.get("date")),
                value_date=None,
                amount=tx_payload["amount"],
                currency=str(row_dict.get("currency", "THB") or "THB"),
                direction=tx_payload["direction"],
                balance_after=tx_payload["balance_after"],
                description_raw=str(row_dict.get("description", "") or "") or None,
                description_normalized=tx_payload["description_normalized"] or None,
                reference_no=tx_payload["reference_no"],
                channel=str(row_dict.get("channel", "") or "") or None,
                transaction_type=tx_payload["transaction_type"],
                counterparty_account_raw=str(row_dict.get("raw_account_value", "") or row_dict.get("counterparty_account", "") or "") or None,
                counterparty_account_normalized=tx_payload["counterparty_account_normalized"],
                counterparty_name_raw=str(row_dict.get("counterparty_name", "") or "") or None,
                counterparty_name_normalized=normalize_text(row_dict.get("counterparty_name", "") or "").lower() or None,
                transaction_fingerprint=tx_payload["transaction_fingerprint"],
                parse_confidence=Decimal(str(row_dict.get("confidence", 0) or 0)).quantize(Decimal("0.0001")),
                duplicate_status=duplicate_status,
                duplicate_group_id=duplicate_group_id,
                review_status="pending" if duplicate_status == "unique" else "needs_review",
                linkage_status="unresolved",
                lineage_json=lineage,
            )
            session.add(transaction)
            persisted_transactions.append(transaction)
            pending_cp_links.append((
                row_dict.get("counterparty_account"),
                str(row_dict.get("counterparty_name", "") or ""),
            ))

            # Batch flush every BATCH_SIZE rows
            if len(persisted_transactions) % BATCH_SIZE == 0:
                session.flush()

        # Final flush for remaining transactions
        session.flush()

        # Batch resolve counterparty accounts
        resolved_cp_cache: dict[str, Any] = {}
        for transaction, (cp_acct_raw, cp_name) in zip(persisted_transactions, pending_cp_links):
            cp_key = normalize_account_number(cp_acct_raw) or ""
            if not cp_key:
                continue
            if cp_key not in resolved_cp_cache:
                resolved_cp_cache[cp_key] = resolve_account(
                    session,
                    bank_name=bank_name,
                    raw_account_number=cp_acct_raw,
                    account_holder_name=cp_name,
                    confidence_score=0.65,
                    notes="counterparty discovered from transaction",
                )
            cp_account = resolved_cp_cache[cp_key]
            if cp_account:
                entity_id = entity_lookup.get(("ACCOUNT", cp_account.normalized_account_number or ""))
                if entity_id:
                    _upsert_account_entity_link(
                        session,
                        account_id=cp_account.id,
                        entity_id=entity_id,
                        link_type="counterparty_seen",
                        confidence_score=Decimal("0.6500"),
                        source_reason="counterparty account from transaction import",
                    )

        generate_matches_for_transactions(session, persisted_transactions)

        parser_run.status = "done"
        parser_run.finished_at = utcnow()
        parser_run.summary_json = {
            "bank_key": bank_key,
            "bank_name": bank_name,
            "subject_account": subject_account,
            "subject_name": effective_subject_name,
            "transaction_count": len(persisted_transactions),
            "statement_batch_id": batch.id,
            "output_dir": str(output_dir),
            "sheet_name": sheet_name,
            "header_row": header_row,
        }
        file_row.bank_detected = bank_key
        file_row.import_status = "processed"
        file_row.parser_version = PARSER_VERSION
        file_row.mapping_profile_id = mapping_profile_id
        session.add(parser_run)
        session.add(file_row)

        export_job = create_export_job(
            session,
            export_type="legacy_account_package",
            filters={
                "file_id": file_id,
                "parser_run_id": parser_run_id,
                "output_dir": str(output_dir),
            },
            created_by=operator or "analyst",
        )
        export_job.status = "done"
        export_job.completed_at = utcnow()
        export_job.output_path = str(output_dir)
        export_job.summary_json = {
            "files": _legacy_account_package_files(output_dir)
        }

        # Generate alerts from graph analysis findings
        try:
            from core.graph_analysis import build_graph_analysis
            from services.alert_service import process_findings
            graph_result = build_graph_analysis(
                session,
                account=subject_account,
                limit=2000,
            )
            findings = graph_result.get("suspicious_findings", [])
            if findings:
                process_findings(
                    session,
                    findings,
                    account_id=subject_account_row.id if subject_account_row else None,
                    parser_run_id=parser_run_id,
                )
        except Exception as alert_err:
            import logging as _log
            _log.getLogger(__name__).warning("Alert generation failed (non-fatal): %s", alert_err)

        session.commit()
