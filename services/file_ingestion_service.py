from __future__ import annotations

import mimetypes
from pathlib import Path
import re
from typing import Any
from uuid import UUID

from sqlalchemy import select

from paths import EVIDENCE_DIR
from persistence.base import get_db_session, utcnow
from persistence.models import FileRecord
from services.fingerprinting import sha256_bytes

_SAFE_FILE_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _normalize_file_id(file_id: str) -> str:
    try:
        normalized = str(UUID(str(file_id))).lower()
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid file identifier for evidence storage") from exc
    if not _SAFE_FILE_ID_RE.fullmatch(normalized):
        raise ValueError("Invalid file identifier for evidence storage")
    return normalized


def _storage_name_for_filename(filename: str | None) -> str:
    suffix = Path(str(filename or "")).suffix.lower()
    if suffix == ".xlsx":
        return "original.xlsx"
    if suffix == ".xls":
        return "original.xls"
    if suffix == ".ofx":
        return "original.ofx"
    if suffix == ".pdf":
        return "original.pdf"
    if suffix == ".png":
        return "original.png"
    if suffix == ".jpg":
        return "original.jpg"
    if suffix == ".jpeg":
        return "original.jpeg"
    if suffix == ".bmp":
        return "original.bmp"
    return "original.dat"


def _canonical_evidence_path(file_record: FileRecord, fallback_filename: str | None = None) -> Path:
    safe_file_id = _normalize_file_id(file_record.id)
    storage_name = _storage_name_for_filename(file_record.original_filename or fallback_filename)
    evidence_root = EVIDENCE_DIR.resolve()
    evidence_path = (evidence_root / safe_file_id / storage_name).resolve()
    if evidence_path != evidence_root and evidence_root not in evidence_path.parents:
        raise ValueError("Invalid evidence path")
    return evidence_path


def _canonical_evidence_exists(file_record: FileRecord, fallback_filename: str | None = None) -> bool:
    return _canonical_evidence_path(file_record, fallback_filename).exists()


def _write_canonical_evidence(file_record: FileRecord, content: bytes, fallback_filename: str | None = None) -> Path:
    evidence_path = _canonical_evidence_path(file_record, fallback_filename)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_bytes(content)
    return evidence_path


def _repair_reused_evidence_file(existing: FileRecord, content: bytes, fallback_filename: str) -> Path:
    safe_file_id = _normalize_file_id(existing.id)

    if _canonical_evidence_exists(existing, fallback_filename):
        canonical_path = _canonical_evidence_path(existing, fallback_filename)
        existing.stored_path = str(canonical_path)
        existing.storage_key = f"{safe_file_id}/{canonical_path.name}"
        existing.import_status = "uploaded"
        return canonical_path

    canonical_path = _write_canonical_evidence(existing, content, fallback_filename)
    existing.stored_path = str(canonical_path)
    existing.storage_key = f"{safe_file_id}/{canonical_path.name}"
    existing.import_status = "uploaded"
    return canonical_path


def persist_upload(
    *,
    content: bytes,
    original_filename: str,
    uploaded_by: str = "analyst",
    mime_type: str | None = None,
) -> dict[str, Any]:
    """Persist uploaded file evidence and return duplicate hints."""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    file_hash = sha256_bytes(content)
    file_id = None

    with get_db_session() as session:
        duplicates = session.scalars(
            select(FileRecord).where(FileRecord.file_hash_sha256 == file_hash).order_by(FileRecord.uploaded_at.desc())
        ).all()
        prior = [
            {
                "file_id": row.id,
                "uploaded_at": row.uploaded_at.isoformat() if row.uploaded_at else None,
                "original_filename": row.original_filename,
                "import_status": row.import_status,
            }
            for row in duplicates[:5]
        ]

        # If exact same file already uploaded, reuse it instead of creating a new record
        if duplicates:
            existing = duplicates[0]
            stored_path = _repair_reused_evidence_file(existing, content, original_filename)
            session.add(existing)
            session.commit()
            return {
                "file_id": existing.id,
                "stored_path": str(stored_path),
                "file_hash_sha256": file_hash,
                "duplicate_file_status": "exact_duplicate",
                "prior_ingestions": prior,
                "reused": True,
            }

        file_row = FileRecord(
            original_filename=original_filename,
            stored_path="",
            storage_key=None,
            file_hash_sha256=file_hash,
            mime_type=mime_type or mimetypes.guess_type(original_filename)[0] or "application/octet-stream",
            file_size_bytes=len(content),
            uploaded_at=utcnow(),
            uploaded_by=uploaded_by or "analyst",
            import_status="uploaded",
            metadata_json={
                "duplicate_policy": "reuse_existing",
            },
        )
        session.add(file_row)
        session.flush()
        file_id = file_row.id

        safe_file_id = _normalize_file_id(file_id)
        evidence_path = _write_canonical_evidence(file_row, content)
        file_row.stored_path = str(evidence_path)
        file_row.storage_key = f"{safe_file_id}/{evidence_path.name}"
        file_row.import_status = "uploaded"
        session.add(file_row)
        session.commit()

    normalized_file_id = _normalize_file_id(file_id)
    storage_name = _storage_name_for_filename(original_filename)
    return {
        "file_id": normalized_file_id,
        "stored_path": str(EVIDENCE_DIR / normalized_file_id / storage_name),
        "file_hash_sha256": file_hash,
        "duplicate_file_status": "unique",
        "prior_ingestions": [],
        "reused": False,
    }


def get_file_record(file_id: str) -> FileRecord | None:
    with get_db_session() as session:
        return session.get(FileRecord, file_id)
