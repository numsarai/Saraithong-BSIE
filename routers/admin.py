"""
routers/admin.py
----------------
Admin API routes for database status, backups, reset, and restore.
"""

from fastapi import APIRouter, Depends, HTTPException
from services.auth_service import require_auth
from fastapi.responses import JSONResponse
from sqlalchemy import func, inspect, select

from persistence.base import DATABASE_RUNTIME_SOURCE, DATABASE_URL, IS_SQLITE, engine, get_db_session
from persistence.models import (
    Account,
    AuditLog,
    DuplicateGroup,
    Entity,
    ExportJob,
    FileRecord,
    MappingProfileRecord,
    ParserRun,
    RawImportRow,
    StatementBatch,
    Transaction,
    TransactionMatch,
)
from persistence.schemas import (
    DatabaseBackupRequest,
    DatabaseBackupSettingsRequest,
    DatabaseResetRequest,
    DatabaseRestoreRequest,
)
from services.admin_service import (
    RESET_CONFIRMATION_TEXT,
    RESTORE_CONFIRMATION_TEXT,
    create_database_backup,
    get_database_backup_preview,
    get_backup_settings,
    list_database_backups,
    reset_database,
    restore_database,
    update_backup_settings,
)
from utils.app_helpers import masked_database_url

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_auth)])


@router.get("/db-status")
async def api_db_status():
    inspector = inspect(engine)
    table_names = sorted(inspector.get_table_names())
    key_counts: dict[str, int] = {}

    with get_db_session() as session:
        count_targets = {
            "files": FileRecord,
            "parser_runs": ParserRun,
            "statement_batches": StatementBatch,
            "raw_import_rows": RawImportRow,
            "accounts": Account,
            "transactions": Transaction,
            "entities": Entity,
            "duplicate_groups": DuplicateGroup,
            "transaction_matches": TransactionMatch,
            "audit_logs": AuditLog,
            "mapping_profiles": MappingProfileRecord,
            "export_jobs": ExportJob,
        }
        for label, model in count_targets.items():
            key_counts[label] = int(session.scalar(select(func.count()).select_from(model)) or 0)

    return JSONResponse(
        {
            "database_configured": bool(DATABASE_URL),
            "database_backend": "sqlite" if IS_SQLITE else "postgresql",
            "database_runtime_source": DATABASE_RUNTIME_SOURCE,
            "database_url_masked": masked_database_url(DATABASE_URL),
            "table_count": len(table_names),
            "tables": table_names,
            "key_record_counts": key_counts,
            "has_investigation_schema": all(
                table in table_names
                for table in [
                    "files",
                    "parser_runs",
                    "statement_batches",
                    "raw_import_rows",
                    "accounts",
                    "transactions",
                    "entities",
                    "transaction_matches",
                    "audit_logs",
                    "export_jobs",
                ]
            ),
        }
    )


@router.get("/backups")
async def api_list_backups():
    return JSONResponse(
        {
            "items": list_database_backups(),
            "settings": get_backup_settings(),
            "reset_confirmation_text": RESET_CONFIRMATION_TEXT,
            "restore_confirmation_text": RESTORE_CONFIRMATION_TEXT,
        }
    )


@router.get("/backup-settings")
async def api_get_backup_settings():
    return JSONResponse(get_backup_settings())


@router.post("/backup-settings")
async def api_update_backup_settings(body: DatabaseBackupSettingsRequest):
    try:
        payload = update_backup_settings(
            enabled=body.enabled,
            interval_hours=body.interval_hours,
            backup_format=body.backup_format,
            retention_enabled=body.retention_enabled,
            retain_count=body.retain_count,
            updated_by=body.updated_by,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return JSONResponse(payload)


@router.get("/backups/{backup_name}/preview")
async def api_backup_preview(backup_name: str):
    try:
        payload = get_database_backup_preview(backup_name)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return JSONResponse(payload)


@router.post("/backup")
async def api_create_backup(body: DatabaseBackupRequest):
    try:
        payload = create_database_backup(operator=body.operator, note=body.note, backup_format=body.backup_format)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    return JSONResponse(payload)


@router.post("/reset")
async def api_reset_database(body: DatabaseResetRequest):
    try:
        payload = reset_database(
            confirm_text=body.confirm_text,
            operator=body.operator,
            note=body.note,
            create_pre_reset_backup=body.create_pre_reset_backup,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return JSONResponse(payload)


@router.post("/restore")
async def api_restore_database(body: DatabaseRestoreRequest):
    try:
        payload = restore_database(
            backup_filename=body.backup_filename,
            confirm_text=body.confirm_text,
            operator=body.operator,
            note=body.note,
            create_pre_restore_backup=body.create_pre_restore_backup,
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    return JSONResponse(payload)
