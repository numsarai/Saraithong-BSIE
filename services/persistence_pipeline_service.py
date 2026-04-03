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

        raw_row_map: dict[int, str] = {}
        for idx, row in raw_df.reset_index(drop=True).iterrows():
            source_row_number = int(row.get("_source_row_number") or (header_row + idx + 2))
            payload = _row_to_json(row)
            raw_row = RawImportRow(
                file_id=file_id,
                parser_run_id=parser_run_id,
                sheet_name=sheet_name,
                source_row_number=source_row_number,
                raw_row_json=payload,
                parsed_status="parsed",
                warning_json=[],
            )
            session.add(raw_row)
            session.flush()
            raw_row_map[source_row_number] = raw_row.id

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
        for _, row in entities_df.fillna("").iterrows():
            entity_type = str(row.get("entity_type", "UNKNOWN") or "UNKNOWN")
            identifier_value = str(row.get("account_number", "") or row.get("name", "") or "UNKNOWN")
            normalized_name = normalize_text(row.get("name", "") or "").lower() or None
            existing = session.scalars(
                select(Entity).where(
                    Entity.entity_type == entity_type,
                    Entity.identifier_value == identifier_value,
                )
            ).first()
            if existing:
                entity_lookup[(entity_type, identifier_value)] = existing.id
                continue
            entity = Entity(
                entity_type=entity_type,
                full_name=str(row.get("name", "") or "") or None,
                normalized_name=normalized_name,
                alias_json=[],
                identifier_value=identifier_value,
                notes=None,
                created_at=utcnow(),
            )
            session.add(entity)
            session.flush()
            entity_lookup[(entity_type, identifier_value)] = entity.id

        if subject_account_row:
            subject_entity_id = entity_lookup.get(("ACCOUNT", subject_account_row.normalized_account_number or ""))
            if subject_entity_id:
                link = AccountEntityLink(
                    account_id=subject_account_row.id,
                    entity_id=subject_entity_id,
                    link_type="owns",
                    confidence_score=Decimal("1.0000"),
                    source_reason="subject account entity",
                    is_manual_confirmed=False,
                    created_at=utcnow(),
                )
                session.add(link)

        persisted_transactions: list[Transaction] = []
        for _, row in tx_df.fillna("").iterrows():
            tx_payload = {
                "account_id": subject_account_row.id if subject_account_row else None,
                "parser_run_id": parser_run_id,
                "transaction_datetime": parse_datetime(row.get("date"), row.get("time")),
                "amount": decimal_or_none(row.get("amount")) or Decimal("0.00"),
                "direction": str(row.get("direction", "") or "UNKNOWN"),
                "description_normalized": normalize_text(row.get("description", "") or "").lower(),
                "reference_no": str(row.get("reference_no", "") or "").strip() or None,
                "counterparty_account_normalized": normalize_account_number(row.get("counterparty_account")),
                "balance_after": decimal_or_none(row.get("balance")),
                "transaction_type": str(row.get("transaction_type", "") or "").strip() or None,
            }
            tx_payload["transaction_fingerprint"] = transaction_fingerprint(tx_payload)
            duplicate_status, duplicate_group_id, duplicate_confidence, duplicate_reason = classify_transaction_duplicate(session, tx_payload)
            source_row_number = int(row.get("_source_row_number") or row.get("row_number") or 0 or 0)
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
                "transaction_record_id": str(row.get("transaction_id", "") or ""),
                "subject_account": subject_account,
                "subject_name": subject_name,
            }
            transaction = Transaction(
                statement_batch_id=batch.id,
                file_id=file_id,
                parser_run_id=parser_run_id,
                source_row_id=raw_row_map.get(source_row_number),
                account_id=subject_account_row.id if subject_account_row else None,
                transaction_datetime=tx_payload["transaction_datetime"],
                posted_date=_to_python_date(row.get("date")),
                value_date=None,
                amount=tx_payload["amount"],
                currency=str(row.get("currency", "THB") or "THB"),
                direction=tx_payload["direction"],
                balance_after=tx_payload["balance_after"],
                description_raw=str(row.get("description", "") or "") or None,
                description_normalized=tx_payload["description_normalized"] or None,
                reference_no=tx_payload["reference_no"],
                channel=str(row.get("channel", "") or "") or None,
                transaction_type=tx_payload["transaction_type"],
                counterparty_account_raw=str(row.get("raw_account_value", "") or row.get("counterparty_account", "") or "") or None,
                counterparty_account_normalized=tx_payload["counterparty_account_normalized"],
                counterparty_name_raw=str(row.get("counterparty_name", "") or "") or None,
                counterparty_name_normalized=normalize_text(row.get("counterparty_name", "") or "").lower() or None,
                transaction_fingerprint=tx_payload["transaction_fingerprint"],
                parse_confidence=Decimal(str(row.get("confidence", 0) or 0)).quantize(Decimal("0.0001")),
                duplicate_status=duplicate_status,
                duplicate_group_id=duplicate_group_id,
                review_status="pending" if duplicate_status == "unique" else "needs_review",
                linkage_status="unresolved",
                lineage_json=lineage,
            )
            session.add(transaction)
            session.flush()
            persisted_transactions.append(transaction)

            cp_account = resolve_account(
                session,
                bank_name=bank_name,
                raw_account_number=row.get("counterparty_account"),
                account_holder_name=str(row.get("counterparty_name", "") or ""),
                confidence_score=0.65,
                notes="counterparty discovered from transaction",
            )
            if cp_account:
                entity_id = entity_lookup.get(("ACCOUNT", cp_account.normalized_account_number or ""))
                if entity_id:
                    session.add(
                        AccountEntityLink(
                            account_id=cp_account.id,
                            entity_id=entity_id,
                            link_type="counterparty_seen",
                            confidence_score=Decimal("0.6500"),
                            source_reason="counterparty account from transaction import",
                            is_manual_confirmed=False,
                            created_at=utcnow(),
                        )
                    )

        generate_matches_for_transactions(session, persisted_transactions)

        parser_run.status = "done"
        parser_run.finished_at = utcnow()
        parser_run.summary_json = {
            "bank_key": bank_key,
            "bank_name": bank_name,
            "subject_account": subject_account,
            "subject_name": subject_name,
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
            "files": [
                "meta.json",
                "processed/transactions.csv",
                "processed/entities.csv",
                "processed/links.csv",
                "processed/nodes.csv",
                "processed/nodes.json",
                "processed/edges.csv",
                "processed/edges.json",
                "processed/aggregated_edges.csv",
                "processed/aggregated_edges.json",
                "processed/derived_account_edges.csv",
                "processed/derived_account_edges.json",
                "processed/graph_manifest.json",
                "processed/suspicious_findings.csv",
                "processed/suspicious_findings.json",
                "processed/i2_chart.anx",
            ]
        }

        session.commit()
