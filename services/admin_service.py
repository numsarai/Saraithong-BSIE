from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import Table, func, select, text
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
