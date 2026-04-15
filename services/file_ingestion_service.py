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

_SAFE_SUFFIX_RE = re.compile(r"^\.[a-z0-9]{1,16}$")


def _normalize_storage_suffix(raw_suffix: str) -> str:
    suffix = (raw_suffix or ".dat").strip().lower()
    return suffix if _SAFE_SUFFIX_RE.fullmatch(suffix) else ".dat"


def _normalize_file_id(file_id: str) -> str:
    try:
        return str(UUID(str(file_id)))
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid file identifier for evidence storage") from exc


def _canonical_evidence_path(file_id: str, suffix: str) -> Path:
    safe_file_id = _normalize_file_id(file_id)
    safe_suffix = _normalize_storage_suffix(suffix)
    evidence_dir = EVIDENCE_DIR / safe_file_id
    if not _is_within_directory(evidence_dir, EVIDENCE_DIR):
        raise ValueError("Resolved evidence directory escaped evidence root")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = evidence_dir / f"original{safe_suffix}"
    if not _is_within_directory(evidence_path, EVIDENCE_DIR):
        raise ValueError("Resolved evidence path escaped evidence root")
    return evidence_path


def _is_within_directory(path: Path, directory: Path) -> bool:
    resolved_path = path.resolve()
    resolved_directory = directory.resolve()
    return resolved_path == resolved_directory or resolved_directory in resolved_path.parents


def _repair_reused_evidence_file(existing: FileRecord, content: bytes, fallback_suffix: str) -> Path:
    stored_path = Path(existing.stored_path) if existing.stored_path else Path()
    suffix = Path(existing.original_filename or "").suffix or fallback_suffix or ".dat"
    canonical_path = _canonical_evidence_path(existing.id, suffix)

    if existing.stored_path:
        try:
            if stored_path.exists() and _is_within_directory(stored_path, EVIDENCE_DIR):
                return stored_path
        except OSError:
            pass

    if not _is_within_directory(canonical_path, EVIDENCE_DIR):
        raise ValueError("Resolved evidence path escaped evidence root")
    canonical_path.write_bytes(content)
    existing.stored_path = str(canonical_path)
    existing.storage_key = f"{_normalize_file_id(existing.id)}/original{_normalize_storage_suffix(suffix)}"
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

        evidence_path = _canonical_evidence_path(file_id, suffix)
        if not _is_within_directory(evidence_path, EVIDENCE_DIR):
            raise ValueError("Resolved evidence path escaped evidence root")
        evidence_path.write_bytes(content)
        file_row.stored_path = str(evidence_path)
        file_row.storage_key = f"{_normalize_file_id(file_id)}/original{suffix}"
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
