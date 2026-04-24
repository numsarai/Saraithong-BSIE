from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import Table, func, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlmodel import SQLModel

from paths import BACKUPS_DIR
from persistence.base import Base, DATABASE_URL, engine, utcnow
from persistence.legacy_models import BankFingerprint, Job, JobMeta, MappingProfile, Override
from persistence.models import (
    Account,
    AccountEntityLink,
    AdminSetting,
    AuditLog,
    BankTemplateVariant,
    CaseTag,
    CaseTagLink,
    DuplicateGroup,
    Entity,
    ExportJob,
    FileRecord,
    MappingProfileRecord,
    ParserRun,
    RawImportRow,
    ReviewDecision,
    StatementBatch,
    Transaction,
    TransactionMatch,
)
from services.audit_service import log_audit

BACKUP_SCHEMA_VERSION = "1.0"
RESET_CONFIRMATION_TEXT = "RESET BSIE DATABASE"
RESTORE_CONFIRMATION_TEXT = "RESTORE BSIE DATABASE"
BACKUP_SETTINGS_KEY = "database_backup"
BACKUP_FORMATS = {"json"}
DEFAULT_BACKUP_RETAIN_COUNT = 20


@dataclass(frozen=True)
class TableSpec:
    name: str
    table: Table


TABLE_SPECS: tuple[TableSpec, ...] = (
    TableSpec("mapping_profiles", MappingProfileRecord.__table__),
    TableSpec("bank_template_variants", BankTemplateVariant.__table__),
    TableSpec("files", FileRecord.__table__),
    TableSpec("parser_runs", ParserRun.__table__),
    TableSpec("accounts", Account.__table__),
    TableSpec("statement_batches", StatementBatch.__table__),
    TableSpec("raw_import_rows", RawImportRow.__table__),
    TableSpec("entities", Entity.__table__),
    TableSpec("account_entity_links", AccountEntityLink.__table__),
    TableSpec("duplicate_groups", DuplicateGroup.__table__),
    TableSpec("transactions", Transaction.__table__),
    TableSpec("transaction_matches", TransactionMatch.__table__),
    TableSpec("review_decisions", ReviewDecision.__table__),
    TableSpec("audit_logs", AuditLog.__table__),
    TableSpec("export_jobs", ExportJob.__table__),
    TableSpec("admin_settings", AdminSetting.__table__),
    TableSpec("case_tags", CaseTag.__table__),
    TableSpec("case_tag_links", CaseTagLink.__table__),
    TableSpec("mapping_profile", MappingProfile.__table__),
    TableSpec("bank_fingerprint", BankFingerprint.__table__),
    TableSpec("override", Override.__table__),
    TableSpec("job", Job.__table__),
    TableSpec("job_meta", JobMeta.__table__),
)


def init_database_on_engine(bind_engine: Engine) -> None:
    """Create all BSIE tables on a provided engine for tests or utilities."""
    Base.metadata.create_all(bind_engine)
    SQLModel.metadata.create_all(bind_engine)


def _safe_backup_dir(backup_dir: Path | None = None) -> Path:
    target = backup_dir or BACKUPS_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def _env_truthy(name: str, default: str = "0") -> bool:
    value = os.getenv(name, default).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _default_backup_settings(bind_engine: Engine | None = None) -> dict[str, Any]:
    bind_engine = bind_engine or engine
    return {
        "enabled": _env_truthy("BSIE_ENABLE_AUTO_BACKUP", "0"),
        "interval_hours": max(1.0, float(os.getenv("BSIE_BACKUP_INTERVAL_HOURS", "24") or "24")),
        "backup_format": "json",
        "retention_enabled": _env_truthy("BSIE_BACKUP_RETENTION_ENABLED", "0"),
        "retain_count": max(1, int(os.getenv("BSIE_BACKUP_RETAIN_COUNT", str(DEFAULT_BACKUP_RETAIN_COUNT)) or str(DEFAULT_BACKUP_RETAIN_COUNT))),
    }


def get_backup_settings(*, bind_engine: Engine | None = None) -> dict[str, Any]:
    bind_engine = bind_engine or engine
    defaults = _default_backup_settings(bind_engine)
    session_factory = _session_factory(bind_engine)
    with session_factory() as session:
        row = session.get(AdminSetting, BACKUP_SETTINGS_KEY)
        if not row:
            effective_format = _resolve_backup_format(defaults["backup_format"], bind_engine)
            return {
                **defaults,
                "effective_backup_format": effective_format,
                "source": "environment_defaults",
                "updated_at": None,
                "updated_by": "system",
            }
        value = row.value_json or {}
        backup_format = str(value.get("backup_format") or defaults["backup_format"]).lower()
        if backup_format not in BACKUP_FORMATS:
            backup_format = defaults["backup_format"]
        effective_format = _resolve_backup_format(backup_format, bind_engine)
        return {
            "enabled": bool(value.get("enabled", defaults["enabled"])),
            "interval_hours": max(1.0, float(value.get("interval_hours", defaults["interval_hours"]))),
            "backup_format": backup_format,
            "retention_enabled": bool(value.get("retention_enabled", defaults["retention_enabled"])),
            "retain_count": max(1, int(value.get("retain_count", defaults["retain_count"]))),
            "effective_backup_format": effective_format,
            "source": "database",
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "updated_by": row.updated_by or "system",
        }


def update_backup_settings(
    *,
    enabled: bool,
    interval_hours: float,
    backup_format: str = "auto",
    retention_enabled: bool = False,
    retain_count: int = DEFAULT_BACKUP_RETAIN_COUNT,
    updated_by: str = "analyst",
    bind_engine: Engine | None = None,
) -> dict[str, Any]:
    bind_engine = bind_engine or engine
    normalized_format = _resolve_backup_format(backup_format, bind_engine)
    interval_hours = max(1.0, float(interval_hours))
    retain_count = max(1, int(retain_count))
    session_factory = _session_factory(bind_engine)
    with session_factory() as session:
        row = session.get(AdminSetting, BACKUP_SETTINGS_KEY)
        old_payload = dict(row.value_json) if row and row.value_json else None
        payload = {
            "enabled": bool(enabled),
            "interval_hours": interval_hours,
            "backup_format": normalized_format,
            "retention_enabled": bool(retention_enabled),
            "retain_count": retain_count,
        }
        if row is None:
            row = AdminSetting(
                key=BACKUP_SETTINGS_KEY,
                value_json=payload,
                updated_at=utcnow(),
                updated_by=updated_by or "analyst",
            )
            session.add(row)
        else:
            row.value_json = payload
            row.updated_at = utcnow()
            row.updated_by = updated_by or "analyst"
        log_audit(
            session,
            object_type="admin_settings",
            object_id=BACKUP_SETTINGS_KEY,
            action_type="update_backup_settings",
            changed_by=updated_by or "analyst",
            old_value=old_payload,
            new_value=payload,
            reason="update backup schedule/settings",
        )
        session.commit()
    return get_backup_settings(bind_engine=bind_engine)


def _mask_database_url(url: str) -> str:
    if "://" not in url or "@" not in url:
        return url
    prefix, rest = url.split("://", 1)
    credentials, suffix = rest.split("@", 1)
    username = credentials.split(":", 1)[0]
    return f"{prefix}://{username}:***@{suffix}"


def _serialize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return {"__bsie_type__": "decimal", "value": str(value)}
    if isinstance(value, datetime):
        return {"__bsie_type__": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"__bsie_type__": "date", "value": value.isoformat()}
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize_value(item) for key, item in value.items()}
    return value


def _deserialize_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_deserialize_value(item) for item in value]
    if isinstance(value, dict):
        marker = value.get("__bsie_type__")
        if marker == "decimal":
            return Decimal(value["value"])
        if marker == "datetime":
            return datetime.fromisoformat(value["value"])
        if marker == "date":
            return date.fromisoformat(value["value"])
        return {key: _deserialize_value(item) for key, item in value.items()}
    return value


def _session_factory(bind_engine: Engine):
    return sessionmaker(
        bind=bind_engine,
        class_=Session,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )


def _count_rows(bind_engine: Engine) -> dict[str, int]:
    counts: dict[str, int] = {}
    with bind_engine.connect() as conn:
        for spec in TABLE_SPECS:
            counts[spec.name] = int(conn.execute(select(func.count()).select_from(spec.table)).scalar_one())
    return counts


def _count_existing_rows(bind_engine: Engine) -> dict[str, int]:
    table_names = set(inspect(bind_engine).get_table_names())
    counts: dict[str, int] = {}
    with bind_engine.connect() as conn:
        for spec in TABLE_SPECS:
            if spec.name not in table_names:
                counts[spec.name] = 0
                continue
            counts[spec.name] = int(conn.execute(select(func.count()).select_from(spec.table)).scalar_one())
    return counts


SAMPLE_FILENAME_CONDITION = """
(
    lower(original_filename) GLOB '*sample*'
    OR lower(original_filename) GLOB '*test*'
    OR lower(original_filename) GLOB '*demo*'
    OR lower(original_filename) GLOB '*dummy*'
    OR lower(original_filename) GLOB '*example*'
    OR lower(original_filename) GLOB '*fixture*'
    OR original_filename GLOB '*ทดสอบ*'
    OR original_filename GLOB '*ตัวอย่าง*'
)
"""


def _fetch_one_mapping(conn, sql: str) -> dict[str, Any]:
    row = conn.execute(text(sql)).mappings().first()
    return dict(row or {})


def _fetch_all_mappings(conn, sql: str) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(text(sql)).mappings().all()]


def _int_value(row: dict[str, Any], key: str) -> int:
    value = row.get(key)
    return int(value or 0)


def _status_counts(rows: list[dict[str, Any]], *, status_key: str, count_key: str) -> dict[str, int]:
    return {str(row.get(status_key) or ""): _int_value(row, count_key) for row in rows}


def _hygiene_check(check_id: str, label: str, count: int, *, severity_when_found: str, detail: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "label": label,
        "count": int(count),
        "status": "attention" if count else "ok",
        "severity": severity_when_found if count else "ok",
        "detail": detail,
    }


def get_data_hygiene_report(*, bind_engine: Engine | None = None) -> dict[str, Any]:
    """Return a read-only database hygiene report for production readiness checks."""
    bind_engine = bind_engine or engine
    with bind_engine.connect() as conn:
        record_counts = _count_existing_rows(bind_engine)
        sample_row = _fetch_one_mapping(
            conn,
            f"""
            WITH file_flags AS (
                SELECT id, {SAMPLE_FILENAME_CONDITION} AS sample_like
                FROM files
            )
            SELECT
                COALESCE(SUM(CASE WHEN sample_like THEN 1 ELSE 0 END), 0) AS sample_like_files,
                COUNT(*) AS total_files
            FROM file_flags
            """,
        )
        sample_txn_row = _fetch_one_mapping(
            conn,
            f"""
            WITH file_flags AS (
                SELECT id, {SAMPLE_FILENAME_CONDITION} AS sample_like
                FROM files
            )
            SELECT COUNT(t.id) AS sample_like_transactions
            FROM file_flags f
            JOIN transactions t ON t.file_id = f.id
            WHERE f.sample_like
            """,
        )
        test_actor_row = _fetch_one_mapping(
            conn,
            """
            SELECT COUNT(*) AS test_actor_files
            FROM files
            WHERE lower(uploaded_by) IN ('tester', 'test', 'fixture')
            """,
        )
        duplicate_hash_row = _fetch_one_mapping(
            conn,
            """
            SELECT COUNT(*) AS duplicate_file_hash_groups, COALESCE(SUM(file_count), 0) AS files_in_duplicate_hash_groups
            FROM (
                SELECT file_hash_sha256, COUNT(*) AS file_count
                FROM files
                GROUP BY file_hash_sha256
                HAVING COUNT(*) > 1
            )
            """,
        )
        parser_status_rows = _fetch_all_mappings(
            conn,
            """
            SELECT status, COUNT(*) AS run_count
            FROM parser_runs
            GROUP BY status
            ORDER BY run_count DESC
            """,
        )
        multiple_runs_row = _fetch_one_mapping(
            conn,
            """
            SELECT COUNT(*) AS files_with_multiple_runs, COALESCE(SUM(run_count), 0) AS runs_on_files_with_multiple_runs
            FROM (
                SELECT file_id, COUNT(*) AS run_count
                FROM parser_runs
                GROUP BY file_id
                HAVING COUNT(*) > 1
            )
            """,
        )
        multiple_done_row = _fetch_one_mapping(
            conn,
            """
            SELECT COUNT(*) AS files_with_multiple_done_runs, COALESCE(SUM(done_runs), 0) AS done_runs_on_those_files
            FROM (
                SELECT file_id, COUNT(*) AS done_runs
                FROM parser_runs
                WHERE status = 'done'
                GROUP BY file_id
                HAVING COUNT(*) > 1
            )
            """,
        )
        stale_run_row = _fetch_one_mapping(
            conn,
            """
            SELECT COUNT(t.id) AS transactions_on_non_done_runs
            FROM transactions t
            JOIN parser_runs pr ON pr.id = t.parser_run_id
            WHERE pr.status <> 'done'
            """,
        )
        orphan_file_row = _fetch_one_mapping(
            conn,
            """
            SELECT COUNT(*) AS files_without_parser_runs
            FROM files f
            LEFT JOIN parser_runs pr ON pr.file_id = f.id
            WHERE pr.id IS NULL
            """,
        )
        duplicate_status_rows = _fetch_all_mappings(
            conn,
            """
            SELECT duplicate_status, COUNT(*) AS txn_count
            FROM transactions
            GROUP BY duplicate_status
            ORDER BY txn_count DESC
            """,
        )
        duplicate_fingerprint_row = _fetch_one_mapping(
            conn,
            """
            SELECT COUNT(*) AS duplicate_fingerprint_groups, COALESCE(SUM(txn_count), 0) AS transactions_in_duplicate_fingerprint_groups
            FROM (
                SELECT transaction_fingerprint, COUNT(*) AS txn_count
                FROM transactions
                WHERE transaction_fingerprint IS NOT NULL AND transaction_fingerprint <> ''
                GROUP BY transaction_fingerprint
                HAVING COUNT(*) > 1
            )
            """,
        )
        same_file_row_duplicate_row = _fetch_one_mapping(
            conn,
            """
            SELECT COUNT(*) AS same_file_row_duplicate_groups, COALESCE(SUM(txn_count), 0) AS transactions_in_same_file_row_duplicate_groups
            FROM (
                SELECT file_id, COALESCE(source_row_id, '') AS source_row_key, COUNT(*) AS txn_count
                FROM transactions
                GROUP BY file_id, COALESCE(source_row_id, '')
                HAVING COUNT(*) > 1 AND COALESCE(source_row_id, '') <> ''
            )
            """,
        )
        repeated_filename_rows = _fetch_all_mappings(
            conn,
            """
            SELECT original_filename, uploaded_by, COUNT(*) AS files, COUNT(DISTINCT file_hash_sha256) AS distinct_hashes
            FROM files
            GROUP BY original_filename, uploaded_by
            HAVING COUNT(*) > 1
            ORDER BY files DESC, original_filename
            LIMIT 20
            """,
        )
        sample_like_rows = _fetch_all_mappings(
            conn,
            f"""
            SELECT
                substr(f.id, 1, 8) AS file_id_prefix,
                f.original_filename,
                f.uploaded_by,
                f.import_status,
                f.uploaded_at,
                COUNT(t.id) AS transactions
            FROM files f
            LEFT JOIN transactions t ON t.file_id = f.id
            WHERE {SAMPLE_FILENAME_CONDITION}
            GROUP BY f.id, f.original_filename, f.uploaded_by, f.import_status, f.uploaded_at
            ORDER BY f.uploaded_at DESC
            LIMIT 30
            """,
        )
        duplicate_fingerprint_file_rows = _fetch_all_mappings(
            conn,
            """
            WITH dup AS (
                SELECT transaction_fingerprint
                FROM transactions
                WHERE transaction_fingerprint IS NOT NULL AND transaction_fingerprint <> ''
                GROUP BY transaction_fingerprint
                HAVING COUNT(*) > 1
            )
            SELECT f.original_filename, COUNT(*) AS duplicate_transactions, COUNT(DISTINCT t.transaction_fingerprint) AS duplicate_groups
            FROM transactions t
            JOIN dup d ON d.transaction_fingerprint = t.transaction_fingerprint
            JOIN files f ON f.id = t.file_id
            GROUP BY f.original_filename
            ORDER BY duplicate_transactions DESC, f.original_filename
            LIMIT 20
            """,
        )

    parser_status_counts = _status_counts(parser_status_rows, status_key="status", count_key="run_count")
    duplicate_status_counts = _status_counts(duplicate_status_rows, status_key="duplicate_status", count_key="txn_count")
    summary = {
        "record_counts": record_counts,
        "sample_like_files": _int_value(sample_row, "sample_like_files"),
        "sample_like_transactions": _int_value(sample_txn_row, "sample_like_transactions"),
        "test_actor_files": _int_value(test_actor_row, "test_actor_files"),
        "duplicate_file_hash_groups": _int_value(duplicate_hash_row, "duplicate_file_hash_groups"),
        "files_in_duplicate_hash_groups": _int_value(duplicate_hash_row, "files_in_duplicate_hash_groups"),
        "parser_run_status_counts": parser_status_counts,
        "files_with_multiple_runs": _int_value(multiple_runs_row, "files_with_multiple_runs"),
        "runs_on_files_with_multiple_runs": _int_value(multiple_runs_row, "runs_on_files_with_multiple_runs"),
        "files_with_multiple_done_runs": _int_value(multiple_done_row, "files_with_multiple_done_runs"),
        "done_runs_on_files_with_multiple_done_runs": _int_value(multiple_done_row, "done_runs_on_those_files"),
        "transactions_on_non_done_runs": _int_value(stale_run_row, "transactions_on_non_done_runs"),
        "files_without_parser_runs": _int_value(orphan_file_row, "files_without_parser_runs"),
        "duplicate_status_counts": duplicate_status_counts,
        "duplicate_fingerprint_groups": _int_value(duplicate_fingerprint_row, "duplicate_fingerprint_groups"),
        "transactions_in_duplicate_fingerprint_groups": _int_value(duplicate_fingerprint_row, "transactions_in_duplicate_fingerprint_groups"),
        "same_file_row_duplicate_groups": _int_value(same_file_row_duplicate_row, "same_file_row_duplicate_groups"),
        "transactions_in_same_file_row_duplicate_groups": _int_value(same_file_row_duplicate_row, "transactions_in_same_file_row_duplicate_groups"),
    }

    checks = [
        _hygiene_check(
            "sample_like_files",
            "Sample/test-like filenames",
            summary["sample_like_files"],
            severity_when_found="warning",
            detail="Files whose names look like sample, test, demo, fixture, ทดสอบ, or ตัวอย่าง.",
        ),
        _hygiene_check(
            "test_actor_files",
            "Files uploaded by test actors",
            summary["test_actor_files"],
            severity_when_found="warning",
            detail="Files uploaded by tester/test/fixture accounts.",
        ),
        _hygiene_check(
            "duplicate_file_hash_groups",
            "Duplicate file hashes",
            summary["duplicate_file_hash_groups"],
            severity_when_found="blocker",
            detail="Same SHA-256 appears in more than one file record.",
        ),
        _hygiene_check(
            "files_with_multiple_done_runs",
            "Multiple done parser runs on one file",
            summary["files_with_multiple_done_runs"],
            severity_when_found="blocker",
            detail="One file has more than one completed parser run.",
        ),
        _hygiene_check(
            "transactions_on_non_done_runs",
            "Transactions attached to non-done runs",
            summary["transactions_on_non_done_runs"],
            severity_when_found="blocker",
            detail="Transactions should not remain attached to failed, queued, or superseded parser runs.",
        ),
        _hygiene_check(
            "same_file_row_duplicate_groups",
            "Same file/source-row transaction duplicates",
            summary["same_file_row_duplicate_groups"],
            severity_when_found="blocker",
            detail="The same source row in a file produced more than one transaction.",
        ),
        _hygiene_check(
            "duplicate_fingerprint_groups",
            "Duplicate transaction fingerprints",
            summary["duplicate_fingerprint_groups"],
            severity_when_found="warning",
            detail="Potential duplicate transaction fingerprints across files/runs for analyst review.",
        ),
        _hygiene_check(
            "queued_or_failed_runs",
            "Queued or failed parser runs",
            parser_status_counts.get("queued", 0) + parser_status_counts.get("failed", 0),
            severity_when_found="warning",
            detail="Parser runs that did not finish cleanly may need review before live operations.",
        ),
        _hygiene_check(
            "files_without_parser_runs",
            "Files without parser runs",
            summary["files_without_parser_runs"],
            severity_when_found="info",
            detail="Uploaded files that have not produced parser runs yet.",
        ),
    ]
    blocker_count = sum(1 for item in checks if item["severity"] == "blocker")
    warning_count = sum(1 for item in checks if item["severity"] == "warning")
    overall_status = "blocked" if blocker_count else "review_required" if warning_count else "ready"

    recommendations: list[str] = []
    if summary["sample_like_files"] or summary["test_actor_files"]:
        recommendations.append("Create a backup, then reset or clean sample/test data before using the current database as a live case repository.")
    if summary["duplicate_file_hash_groups"] == 0 and summary["files_with_multiple_done_runs"] == 0 and summary["transactions_on_non_done_runs"] == 0:
        recommendations.append("No evidence of repeated-file processing accumulating stale transactions was found.")
    if summary["duplicate_fingerprint_groups"]:
        recommendations.append("Review duplicate transaction fingerprint groups; they may be legitimate mirrored statements or duplicate evidence packages.")
    if parser_status_counts.get("queued", 0) or parser_status_counts.get("failed", 0):
        recommendations.append("Review queued/failed parser runs and clear or reprocess them before operational rollout.")
    if not recommendations:
        recommendations.append("Database hygiene checks are clean for pilot use.")

    return {
        "generated_at": utcnow().isoformat(),
        "read_only": True,
        "overall_status": overall_status,
        "blocker_count": blocker_count,
        "warning_count": warning_count,
        "summary": summary,
        "checks": checks,
        "samples": {
            "sample_like_files": sample_like_rows,
            "repeated_filenames": repeated_filename_rows,
            "duplicate_fingerprint_files": duplicate_fingerprint_file_rows,
        },
        "recommendations": recommendations,
    }


def _resolve_backup_format(requested_format: str | None, bind_engine: Engine) -> str:
    _ = bind_engine
    normalized = (requested_format or "json").strip().lower()
    if normalized in {"", "auto", "json"}:
        return "json"
    raise ValueError(f"backup_format must be one of {sorted(BACKUP_FORMATS)}")


def _prune_old_backups(
    *,
    retain_count: int,
    backup_dir: Path | None = None,
) -> list[str]:
    retain_count = max(1, int(retain_count))
    items = list_database_backups(backup_dir=backup_dir)
    removed: list[str] = []
    for item in items[retain_count:]:
        filename = str(item.get("filename", "") or "")
        if not filename:
            continue
        base = _safe_backup_dir(backup_dir)
        candidates = [base / filename, base / f"{filename}.manifest.json"]
        for candidate in candidates:
            if candidate.exists():
                candidate.unlink()
        removed.append(filename)
    return removed


def _build_backup_manifest(
    *,
    bind_engine: Engine,
    backup_id: str,
    created_at: datetime,
    operator: str,
    note: str,
    filename: str,
    backup_format: str,
    path: Path,
    ) -> dict[str, Any]:
    table_counts = _count_rows(bind_engine)
    return {
        "backup_id": backup_id,
        "schema_version": BACKUP_SCHEMA_VERSION,
        "created_at": created_at.isoformat(),
        "created_by": operator or "analyst",
        "note": note,
        "database_backend": bind_engine.dialect.name,
        "database_url_masked": _mask_database_url(str(bind_engine.url) if bind_engine is not engine else DATABASE_URL),
        "table_counts": table_counts,
        "total_rows": sum(table_counts.values()),
        "filename": filename,
        "path": str(path),
        "backup_format": backup_format,
    }


def list_database_backups(*, backup_dir: Path | None = None) -> list[dict[str, Any]]:
    target = _safe_backup_dir(backup_dir)
    items: list[dict[str, Any]] = []
    candidate_paths = sorted(target.glob("bsie_backup_*.json"), reverse=True)
    seen_filenames: set[str] = set()
    for path in candidate_paths:
        backup_filename = path.name
        if backup_filename in seen_filenames:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        seen_filenames.add(backup_filename)
        items.append(
            {
                "backup_id": payload.get("backup_id", ""),
                "filename": backup_filename,
                "created_at": payload.get("created_at"),
                "created_by": payload.get("created_by"),
                "note": payload.get("note", ""),
                "database_backend": payload.get("database_backend"),
                "database_url_masked": payload.get("database_url_masked"),
                "table_counts": payload.get("table_counts", {}),
                "total_rows": payload.get("total_rows", 0),
                "backup_format": payload.get("backup_format", "json"),
            }
        )
    items.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return items


def get_database_backup_preview(
    backup_filename: str,
    *,
    bind_engine: Engine | None = None,
    backup_dir: Path | None = None,
) -> dict[str, Any]:
    bind_engine = bind_engine or engine
    target = _safe_backup_dir(backup_dir)
    backup_path = (target / Path(backup_filename).name).resolve()
    if backup_path.parent != target.resolve() or backup_path.suffix != ".json" or not backup_path.exists():
        raise FileNotFoundError("Backup file not found")

    payload = json.loads(backup_path.read_text(encoding="utf-8"))
    current_counts = _count_rows(bind_engine)
    backup_counts = payload.get("table_counts", {})
    delta_counts = {
        name: int(backup_counts.get(name, 0)) - int(current_counts.get(name, 0))
        for name in {**current_counts, **backup_counts}
    }
    return {
        "backup_id": payload.get("backup_id", ""),
        "filename": backup_path.name,
        "created_at": payload.get("created_at"),
        "created_by": payload.get("created_by"),
        "note": payload.get("note", ""),
        "database_backend": payload.get("database_backend"),
        "database_url_masked": payload.get("database_url_masked"),
        "schema_version": payload.get("schema_version"),
        "backup_format": payload.get("backup_format", "json"),
        "total_rows": payload.get("total_rows", 0),
        "backup_table_counts": backup_counts,
        "current_table_counts": current_counts,
        "delta_table_counts": delta_counts,
        "will_replace_current_data": any(current_counts.values()),
    }


def create_database_backup(
    *,
    operator: str = "analyst",
    note: str = "",
    backup_format: str = "auto",
    bind_engine: Engine | None = None,
    backup_dir: Path | None = None,
) -> dict[str, Any]:
    bind_engine = bind_engine or engine
    target = _safe_backup_dir(backup_dir)
    created_at = utcnow()
    _resolve_backup_format(backup_format, bind_engine)
    settings = get_backup_settings(bind_engine=bind_engine)
    backup_id = str(uuid4())
    filename = f"bsie_backup_{created_at.strftime('%Y%m%d_%H%M%S')}_{backup_id[:8]}.json"
    path = target / filename

    payload: dict[str, Any] = {
        **_build_backup_manifest(
            bind_engine=bind_engine,
            backup_id=backup_id,
            created_at=created_at,
            operator=operator,
            note=note,
            filename=filename,
            backup_format="json",
            path=path,
        ),
        "tables": {},
    }

    with bind_engine.connect() as conn:
        for spec in TABLE_SPECS:
            rows = [dict(row) for row in conn.execute(select(spec.table)).mappings().all()]
            serialized_rows = [{key: _serialize_value(value) for key, value in row.items()} for row in rows]
            payload["tables"][spec.name] = serialized_rows

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    result = {
        "backup_id": backup_id,
        "filename": filename,
        "path": str(path),
        "created_at": payload["created_at"],
        "created_by": payload["created_by"],
        "note": note,
        "database_backend": payload["database_backend"],
        "table_counts": payload["table_counts"],
        "total_rows": payload["total_rows"],
        "backup_format": "json",
    }
    result["pruned_backups"] = _prune_old_backups(retain_count=settings["retain_count"], backup_dir=backup_dir) if settings.get("retention_enabled") else []
    return result


def maybe_run_scheduled_backup(
    *,
    interval_hours: float | None = None,
    backup_format: str | None = None,
    operator: str = "system",
    backup_dir: Path | None = None,
    bind_engine: Engine | None = None,
) -> dict[str, Any] | None:
    bind_engine = bind_engine or engine
    settings = get_backup_settings(bind_engine=bind_engine)
    enabled = settings["enabled"] if interval_hours is None and backup_format is None else True
    effective_interval = interval_hours if interval_hours is not None else float(settings["interval_hours"])
    effective_format = backup_format or settings["backup_format"]
    if not enabled:
        return None
    if effective_interval <= 0:
        return None
    backups = list_database_backups(backup_dir=backup_dir)
    now = utcnow()
    if backups:
        latest_created_at = backups[0].get("created_at")
        if latest_created_at:
            latest_dt = datetime.fromisoformat(str(latest_created_at))
            if latest_dt.tzinfo is None:
                latest_dt = latest_dt.replace(tzinfo=now.tzinfo)
            if now - latest_dt < timedelta(hours=effective_interval):
                return None
    return create_database_backup(
        operator=operator,
        note=f"scheduled backup every {effective_interval:g} hours",
        backup_format=effective_format,
        bind_engine=bind_engine,
        backup_dir=backup_dir,
    )


def _clear_database(bind_engine: Engine) -> None:
    with bind_engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.execute(text("UPDATE accounts SET merged_into_account_id = NULL"))
        for spec in reversed(TABLE_SPECS):
            conn.execute(spec.table.delete())
        conn.execute(text("PRAGMA foreign_keys=ON"))


def reset_database(
    *,
    confirm_text: str,
    operator: str = "analyst",
    note: str = "",
    create_pre_reset_backup: bool = True,
    bind_engine: Engine | None = None,
    backup_dir: Path | None = None,
) -> dict[str, Any]:
    if confirm_text.strip() != RESET_CONFIRMATION_TEXT:
        raise ValueError(f'Confirmation text must be exactly "{RESET_CONFIRMATION_TEXT}"')

    bind_engine = bind_engine or engine
    pre_backup = None
    if create_pre_reset_backup:
        pre_backup = create_database_backup(
            operator=operator,
            note=note or "automatic pre-reset backup",
            bind_engine=bind_engine,
            backup_dir=backup_dir,
        )

    _clear_database(bind_engine)
    return {
        "status": "ok",
        "pre_reset_backup": pre_backup,
        "table_counts": _count_rows(bind_engine),
    }


def restore_database(
    *,
    backup_filename: str,
    confirm_text: str,
    operator: str = "analyst",
    note: str = "",
    create_pre_restore_backup: bool = True,
    bind_engine: Engine | None = None,
    backup_dir: Path | None = None,
) -> dict[str, Any]:
    if confirm_text.strip() != RESTORE_CONFIRMATION_TEXT:
        raise ValueError(f'Confirmation text must be exactly "{RESTORE_CONFIRMATION_TEXT}"')

    bind_engine = bind_engine or engine
    target = _safe_backup_dir(backup_dir)
    backup_path = (target / Path(backup_filename).name).resolve()
    if backup_path.parent != target.resolve() or backup_path.suffix != ".json" or not backup_path.exists():
        raise FileNotFoundError("Backup file not found")

    payload = json.loads(backup_path.read_text(encoding="utf-8"))
    backup_format = payload.get("backup_format", "json")
    if backup_format != "json":
        raise ValueError("Only JSON backups are supported by the local-only runtime")

    pre_backup = None
    current_counts = _count_rows(bind_engine)
    if create_pre_restore_backup and any(current_counts.values()):
        pre_backup = create_database_backup(
            operator=operator,
            note=note or f"automatic pre-restore backup before {backup_path.name}",
            bind_engine=bind_engine,
            backup_dir=backup_dir,
        )

    _clear_database(bind_engine)
    with bind_engine.begin() as conn:
        for spec in TABLE_SPECS:
            rows = payload.get("tables", {}).get(spec.name, [])
            if not rows:
                continue
            decoded_rows = [
                {key: _deserialize_value(value) for key, value in row.items()}
                for row in rows
            ]
            conn.execute(spec.table.insert(), decoded_rows)

    session_factory = _session_factory(bind_engine)
    with session_factory() as session:
        log_audit(
            session,
            object_type="system",
            object_id="database",
            action_type="database_restore",
            changed_by=operator or "analyst",
            new_value={
                "backup_filename": backup_path.name,
                "backup_id": payload.get("backup_id"),
                "restored_at": utcnow().isoformat(),
            },
            reason=note or f"restored {backup_path.name}",
            extra_context={"pre_restore_backup": pre_backup["filename"] if pre_backup else None},
        )
        session.commit()

    return {
        "status": "ok",
        "restored_backup": backup_path.name,
        "pre_restore_backup": pre_backup,
        "table_counts": _count_rows(bind_engine),
    }
