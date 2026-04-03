from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _legacy_utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MappingProfile(SQLModel, table=True):
    __tablename__ = "mapping_profile"

    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: str = Field(index=True, unique=True)
    bank: str = Field(index=True)
    columns_json: str
    columns_signature: str = Field(index=True, unique=True)
    mapping_json: str
    usage_count: int = Field(default=0)
    last_used: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=_legacy_utcnow)

    @property
    def columns(self):
        return json.loads(self.columns_json)

    @property
    def mapping(self):
        return json.loads(self.mapping_json)

    def to_dict(self):
        return {
            "profile_id": self.profile_id,
            "bank": self.bank,
            "columns": self.columns,
            "columns_signature": self.columns_signature,
            "mapping": self.mapping,
            "usage_count": self.usage_count,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class BankFingerprint(SQLModel, table=True):
    __tablename__ = "bank_fingerprint"

    id: Optional[int] = Field(default=None, primary_key=True)
    fingerprint_id: str = Field(index=True, unique=True)
    bank_key: str = Field(index=True)
    columns_json: str
    ordered_signature: str = Field(index=True)
    set_signature: str = Field(index=True)
    header_row: int = Field(default=0)
    sheet_name: str = Field(default="")
    usage_count: int = Field(default=0)
    last_used: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=_legacy_utcnow)

    @property
    def columns(self):
        return json.loads(self.columns_json)

    def to_dict(self):
        return {
            "fingerprint_id": self.fingerprint_id,
            "bank_key": self.bank_key,
            "columns": self.columns,
            "ordered_signature": self.ordered_signature,
            "set_signature": self.set_signature,
            "header_row": self.header_row,
            "sheet_name": self.sheet_name,
            "usage_count": self.usage_count,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Override(SQLModel, table=True):
    __tablename__ = "override"

    id: Optional[int] = Field(default=None, primary_key=True)
    transaction_id: str = Field(index=True, unique=True)
    override_from_account: str
    override_to_account: str
    override_reason: str = Field(default="")
    override_by: str = Field(default="analyst")
    override_timestamp: datetime = Field(default_factory=_legacy_utcnow)

    def to_dict(self):
        return {
            "transaction_id": self.transaction_id,
            "override_from_account": self.override_from_account,
            "override_to_account": self.override_to_account,
            "override_reason": self.override_reason,
            "override_by": self.override_by,
            "override_timestamp": self.override_timestamp.isoformat() if self.override_timestamp else None,
        }


class Job(SQLModel, table=True):
    __tablename__ = "job"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: str = Field(index=True, unique=True)
    status: str = Field(default="queued", index=True)
    log_text: str = Field(default="")
    result_json: Optional[str] = Field(default=None)
    error: Optional[str] = Field(default=None)
    account: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=_legacy_utcnow)
    updated_at: datetime = Field(default_factory=_legacy_utcnow)


class JobMeta(SQLModel, table=True):
    __tablename__ = "job_meta"

    id: Optional[int] = Field(default=None, primary_key=True)
    account_number: str = Field(index=True)
    job_id: str = Field(index=True)
    bank: str = Field(default="")
    total_in: float = Field(default=0.0)
    total_out: float = Field(default=0.0)
    total_circulation: float = Field(default=0.0)
    num_transactions: int = Field(default=0)
    date_range: str = Field(default="")
    num_unknown: int = Field(default=0)
    num_partial_accounts: int = Field(default=0)
    report_filename: str = Field(default="")
    created_at: datetime = Field(default_factory=_legacy_utcnow)
