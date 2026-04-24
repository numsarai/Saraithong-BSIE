from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from persistence.base import Base, utcnow


def _uuid() -> str:
    return str(uuid.uuid4())


class FileRecord(Base):
    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(1024))
    file_hash_sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(255))
    file_size_bytes: Mapped[int] = mapped_column(nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    uploaded_by: Mapped[str] = mapped_column(String(255), default="analyst", nullable=False)
    bank_detected: Mapped[str | None] = mapped_column(String(64))
    import_status: Mapped[str] = mapped_column(String(64), default="uploaded", nullable=False)
    parser_version: Mapped[str | None] = mapped_column(String(64))
    mapping_profile_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("mapping_profiles.id"))
    notes: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)

    parser_runs: Mapped[list["ParserRun"]] = relationship(back_populates="file")


class MappingProfileRecord(Base):
    __tablename__ = "mapping_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    bank_name: Mapped[str] = mapped_column(String(128), nullable=False)
    profile_name: Mapped[str] = mapped_column(String(255), nullable=False)
    profile_version: Mapped[str] = mapped_column(String(64), nullable=False)
    column_mapping_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    transformation_rules_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    columns_signature: Mapped[str | None] = mapped_column(String(64), index=True)
    source_legacy_profile_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class BankTemplateVariant(Base):
    __tablename__ = "bank_template_variants"
    __table_args__ = (
        UniqueConstraint(
            "bank_key",
            "source_type",
            "ordered_signature",
            "sheet_name",
            "header_row",
            name="uq_bank_template_variant_signature",
        ),
        Index("ix_bank_template_variants_bank_trust", "bank_key", "trust_state"),
        Index("ix_bank_template_variants_set_signature", "set_signature"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    bank_key: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), default="excel", nullable=False)
    sheet_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    header_row: Mapped[int] = mapped_column(default=0, nullable=False)
    ordered_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    set_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    layout_type: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    column_order_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    confirmed_mapping_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    trust_state: Mapped[str] = mapped_column(String(32), default="candidate", nullable=False, index=True)
    usage_count: Mapped[int] = mapped_column(default=0, nullable=False)
    confirmation_count: Mapped[int] = mapped_column(default=0, nullable=False)
    correction_count: Mapped[int] = mapped_column(default=0, nullable=False)
    confirmed_by_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    dry_run_summary_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    promoted_by: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)


class ParserRun(Base):
    __tablename__ = "parser_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    file_id: Mapped[str] = mapped_column(String(36), ForeignKey("files.id"), nullable=False, index=True)
    parser_version: Mapped[str] = mapped_column(String(64), nullable=False)
    mapping_profile_version: Mapped[str | None] = mapped_column(String(64))
    mapping_profile_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("mapping_profiles.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(64), default="queued", nullable=False, index=True)
    bank_detected: Mapped[str | None] = mapped_column(String(64))
    warning_count: Mapped[int] = mapped_column(default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(default=0, nullable=False)
    summary_json: Mapped[dict | None] = mapped_column(JSON)

    file: Mapped[FileRecord] = relationship(back_populates="parser_runs")
    statement_batches: Mapped[list["StatementBatch"]] = relationship(back_populates="parser_run")


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("bank_code", "normalized_account_number", name="uq_accounts_bank_normalized"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    bank_name: Mapped[str | None] = mapped_column(String(128))
    bank_code: Mapped[str | None] = mapped_column(String(32))
    raw_account_number: Mapped[str | None] = mapped_column(String(255))
    normalized_account_number: Mapped[str | None] = mapped_column(String(32), index=True)
    display_account_number: Mapped[str | None] = mapped_column(String(64))
    account_holder_name: Mapped[str | None] = mapped_column(String(255))
    account_type: Mapped[str | None] = mapped_column(String(64))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("1.0000"), nullable=False)
    source_count: Mapped[int] = mapped_column(default=1, nullable=False)
    merged_into_account_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("accounts.id"))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class StatementBatch(Base):
    __tablename__ = "statement_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    file_id: Mapped[str] = mapped_column(String(36), ForeignKey("files.id"), nullable=False, index=True)
    parser_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("parser_runs.id"), nullable=False, index=True)
    account_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("accounts.id"), index=True)
    statement_start_date: Mapped[date | None] = mapped_column(Date)
    statement_end_date: Mapped[date | None] = mapped_column(Date)
    opening_balance: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    closing_balance: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    debit_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    credit_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    transaction_count: Mapped[int] = mapped_column(default=0, nullable=False)
    batch_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    overlap_status: Mapped[str] = mapped_column(String(64), default="new", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    parser_run: Mapped[ParserRun] = relationship(back_populates="statement_batches")


class RawImportRow(Base):
    __tablename__ = "raw_import_rows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    file_id: Mapped[str] = mapped_column(String(36), ForeignKey("files.id"), nullable=False, index=True)
    parser_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("parser_runs.id"), nullable=False, index=True)
    sheet_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_row_number: Mapped[int] = mapped_column(nullable=False)
    raw_row_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    parsed_status: Mapped[str] = mapped_column(String(64), default="pending", nullable=False)
    warning_json: Mapped[list | dict | None] = mapped_column(JSON)


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255))
    normalized_name: Mapped[str | None] = mapped_column(String(255), index=True)
    alias_json: Mapped[list | None] = mapped_column(JSON)
    identifier_value: Mapped[str | None] = mapped_column(String(255), index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AccountEntityLink(Base):
    __tablename__ = "account_entity_links"
    __table_args__ = (
        UniqueConstraint("account_id", "entity_id", "link_type", name="uq_account_entity_link"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("accounts.id"), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("entities.id"), nullable=False, index=True)
    link_type: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("1.0000"), nullable=False)
    source_reason: Mapped[str | None] = mapped_column(Text)
    is_manual_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class DuplicateGroup(Base):
    __tablename__ = "duplicate_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    duplicate_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.0000"), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_status: Mapped[str] = mapped_column(String(64), default="pending", nullable=False)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_account_datetime", "account_id", "transaction_datetime"),
        Index("ix_transactions_posted_date", "posted_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    statement_batch_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("statement_batches.id"), index=True)
    file_id: Mapped[str] = mapped_column(String(36), ForeignKey("files.id"), nullable=False, index=True)
    parser_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("parser_runs.id"), nullable=False, index=True)
    source_row_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("raw_import_rows.id"), index=True)
    account_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("accounts.id"), index=True)
    transaction_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    posted_date: Mapped[date | None] = mapped_column(Date)
    value_date: Mapped[date | None] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(16), default="THB", nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    balance_after: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    description_raw: Mapped[str | None] = mapped_column(Text)
    description_normalized: Mapped[str | None] = mapped_column(Text)
    reference_no: Mapped[str | None] = mapped_column(String(255), index=True)
    channel: Mapped[str | None] = mapped_column(String(255))
    transaction_type: Mapped[str | None] = mapped_column(String(64), index=True)
    counterparty_account_raw: Mapped[str | None] = mapped_column(String(255))
    counterparty_account_normalized: Mapped[str | None] = mapped_column(String(32), index=True)
    counterparty_name_raw: Mapped[str | None] = mapped_column(String(255))
    counterparty_name_normalized: Mapped[str | None] = mapped_column(String(255), index=True)
    transaction_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    parse_confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.0000"), nullable=False)
    duplicate_status: Mapped[str] = mapped_column(String(64), default="unique", nullable=False, index=True)
    duplicate_group_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("duplicate_groups.id"), index=True)
    review_status: Mapped[str] = mapped_column(String(64), default="pending", nullable=False, index=True)
    linkage_status: Mapped[str] = mapped_column(String(64), default="unresolved", nullable=False, index=True)
    lineage_json: Mapped[dict | None] = mapped_column(JSON)
    analyst_note: Mapped[str | None] = mapped_column(Text)


class TransactionMatch(Base):
    __tablename__ = "transaction_matches"
    __table_args__ = (
        Index("ix_transaction_matches_source", "source_transaction_id"),
        Index("ix_transaction_matches_target", "target_transaction_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_transaction_id: Mapped[str] = mapped_column(String(36), ForeignKey("transactions.id"), nullable=False)
    target_transaction_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("transactions.id"))
    target_account_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("accounts.id"))
    match_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.0000"), nullable=False)
    evidence_json: Mapped[dict | list | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(64), default="suggested", nullable=False, index=True)
    is_manual_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    object_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    decision_type: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_value: Mapped[str] = mapped_column(String(255), nullable=False)
    reviewer: Mapped[str] = mapped_column(String(255), default="analyst", nullable=False)
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_object", "object_type", "object_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    object_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(255))
    old_value_json: Mapped[dict | list | str | None] = mapped_column(JSON)
    new_value_json: Mapped[dict | list | str | None] = mapped_column(JSON)
    changed_by: Mapped[str] = mapped_column(String(255), default="analyst", nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    extra_context_json: Mapped[dict | list | None] = mapped_column(JSON)


class ExportJob(Base):
    __tablename__ = "export_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    export_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    filters_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="queued", nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(255), default="analyst", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    output_path: Mapped[str | None] = mapped_column(String(1024))
    summary_json: Mapped[dict | None] = mapped_column(JSON)


class AdminSetting(Base):
    __tablename__ = "admin_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_by: Mapped[str] = mapped_column(String(255), default="system", nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="analyst", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    oauth_provider: Mapped[str | None] = mapped_column(String(64))
    oauth_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GraphAnnotation(Base):
    __tablename__ = "graph_annotations"
    __table_args__ = (
        Index("ix_graph_annotations_node_id", "node_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    node_id: Mapped[str] = mapped_column(String(128), nullable=False)
    annotation_type: Mapped[str] = mapped_column(String(32), default="note", nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    tag: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(255), default="analyst", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_status", "status"),
        Index("ix_alerts_severity", "severity"),
        Index("ix_alerts_rule_type", "rule_type"),
        Index("ix_alerts_account_id", "account_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    transaction_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("transactions.id"), index=True)
    account_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("accounts.id"))
    parser_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("parser_runs.id"))
    rule_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.0000"), nullable=False)
    finding_id: Mapped[str | None] = mapped_column(String(128))
    summary: Mapped[str | None] = mapped_column(Text)
    evidence_json: Mapped[dict | list | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="new", nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(255))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class CaseTag(Base):
    __tablename__ = "case_tags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tag: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class CaseTagLink(Base):
    __tablename__ = "case_tag_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_tag_id: Mapped[str] = mapped_column(String(36), ForeignKey("case_tags.id"), nullable=False, index=True)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    object_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
