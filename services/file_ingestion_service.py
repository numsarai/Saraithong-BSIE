from __future__ import annotations

import mimetypes
import os
from pathlib import Path
import re
from typing import Any
from uuid import UUID

from sqlalchemy import select

from paths import EVIDENCE_DIR
from persistence.base import get_db_session, utcnow
from persistence.models import FileRecord
from services.fingerprinting import sha256_bytes

_SAFE_SUFFIX_RE = re.compile(r"^\.[a-z0-9]{1,16}$")
_SAFE_FILE_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _normalize_storage_suffix(raw_suffix: str) -> str:
    suffix = (raw_suffix or ".dat").strip().lower()
    return suffix if _SAFE_SUFFIX_RE.fullmatch(suffix) else ".dat"


def _normalize_file_id(file_id: str) -> str:
    try:
        normalized = str(UUID(str(file_id))).lower()
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid file identifier for evidence storage") from exc
    if not _SAFE_FILE_ID_RE.fullmatch(normalized):
        raise ValueError("Invalid file identifier for evidence storage")
    return normalized


def _canonical_evidence_path(file_id: str, suffix: str) -> Path:
    safe_file_id = _normalize_file_id(file_id)
    safe_suffix = _normalize_storage_suffix(suffix)
    return EVIDENCE_DIR / safe_file_id / f"original{safe_suffix}"


def _canonical_evidence_exists(file_id: str, suffix: str) -> bool:
    safe_file_id = _normalize_file_id(file_id)
    safe_suffix = _normalize_storage_suffix(suffix)
    evidence_root = os.path.realpath(os.fspath(EVIDENCE_DIR))
    evidence_path = os.path.realpath(os.path.join(os.fspath(EVIDENCE_DIR), safe_file_id, f"original{safe_suffix}"))
    if evidence_path != evidence_root and not evidence_path.startswith(evidence_root + os.sep):
        raise ValueError("Invalid evidence path")
    return os.path.exists(evidence_path)


def _write_canonical_evidence(file_id: str, suffix: str, content: bytes) -> Path:
    safe_file_id = _normalize_file_id(file_id)
    safe_suffix = _normalize_storage_suffix(suffix)
    evidence_root = os.path.realpath(os.fspath(EVIDENCE_DIR))
    evidence_dir = os.path.realpath(os.path.join(os.fspath(EVIDENCE_DIR), safe_file_id))
    if evidence_dir != evidence_root and not evidence_dir.startswith(evidence_root + os.sep):
        raise ValueError("Invalid evidence directory")
    os.makedirs(evidence_dir, exist_ok=True)

    evidence_path = os.path.realpath(os.path.join(evidence_dir, f"original{safe_suffix}"))
    if evidence_path != evidence_root and not evidence_path.startswith(evidence_root + os.sep):
        raise ValueError("Invalid evidence path")

    with open(evidence_path, "wb") as handle:
        handle.write(content)
    return Path(evidence_path)


def _repair_reused_evidence_file(existing: FileRecord, content: bytes, fallback_suffix: str) -> Path:
    suffix = Path(existing.original_filename or "").suffix or fallback_suffix or ".dat"
    safe_file_id = _normalize_file_id(existing.id)
    safe_suffix = _normalize_storage_suffix(suffix)

    if _canonical_evidence_exists(safe_file_id, safe_suffix):
        canonical_path = _canonical_evidence_path(safe_file_id, safe_suffix)
        existing.stored_path = str(canonical_path)
        existing.storage_key = f"{safe_file_id}/original{safe_suffix}"
        existing.import_status = "uploaded"
        return canonical_path

    canonical_path = _write_canonical_evidence(safe_file_id, safe_suffix, content)
    existing.stored_path = str(canonical_path)
    existing.storage_key = f"{safe_file_id}/original{safe_suffix}"
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
    suffix = _normalize_storage_suffix(Path(original_filename).suffix or ".dat")
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
            stored_path = _repair_reused_evidence_file(existing, content, suffix)
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
        evidence_path = _write_canonical_evidence(safe_file_id, suffix, content)
        file_row.stored_path = str(evidence_path)
        file_row.storage_key = f"{safe_file_id}/original{suffix}"
        file_row.import_status = "uploaded"
        session.add(file_row)
        session.commit()

    normalized_file_id = _normalize_file_id(file_id)
    return {
        "file_id": normalized_file_id,
        "stored_path": str(EVIDENCE_DIR / normalized_file_id / f"original{suffix}"),
        "file_hash_sha256": file_hash,
        "duplicate_file_status": "unique",
        "prior_ingestions": [],
        "reused": False,
    }


def get_file_record(file_id: str) -> FileRecord | None:
    with get_db_session() as session:
        return session.get(FileRecord, file_id)
