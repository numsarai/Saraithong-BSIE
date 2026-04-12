from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

from sqlalchemy import select

from paths import EVIDENCE_DIR
from persistence.base import get_db_session, utcnow
from persistence.models import FileRecord
from services.fingerprinting import sha256_bytes


def persist_upload(
    *,
    content: bytes,
    original_filename: str,
    uploaded_by: str = "analyst",
    mime_type: str | None = None,
) -> dict[str, Any]:
    """Persist uploaded file evidence and return duplicate hints."""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(original_filename).suffix or ".dat"
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
            return {
                "file_id": existing.id,
                "stored_path": existing.stored_path,
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

        evidence_dir = EVIDENCE_DIR / file_id
        evidence_dir.mkdir(parents=True, exist_ok=True)
        evidence_path = evidence_dir / f"original{suffix.lower()}"
        evidence_path.write_bytes(content)
        file_row.stored_path = str(evidence_path)
        file_row.storage_key = f"{file_id}/original{suffix.lower()}"
        file_row.import_status = "uploaded"
        session.add(file_row)
        session.commit()

    return {
        "file_id": file_id,
        "stored_path": str(EVIDENCE_DIR / file_id / f"original{suffix.lower()}"),
        "file_hash_sha256": file_hash,
        "duplicate_file_status": "unique",
        "prior_ingestions": [],
        "reused": False,
    }


def get_file_record(file_id: str) -> FileRecord | None:
    with get_db_session() as session:
        return session.get(FileRecord, file_id)
