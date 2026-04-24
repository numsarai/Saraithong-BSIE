from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MappingConfirmRequest(BaseModel):
    bank: str = "UNKNOWN"
    mapping: dict[str, str | None]
    columns: list[str] = Field(default_factory=list)
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)
    source_type: str = "excel"
    layout_type: str = ""
    header_row: int = 0
    sheet_name: str = ""
    reviewer: str = "analyst"
    detected_bank: Any | None = None
    suggested_mapping: dict[str, str | None] = Field(default_factory=dict)
    subject_account: str = ""
    subject_name: str = ""
    identity_guess: Any | None = None
    promote_shared: bool = False


class MappingPreviewRequest(BaseModel):
    bank: str = "UNKNOWN"
    mapping: dict[str, str | None]
    columns: list[str] = Field(default_factory=list)
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)


class MappingAssistRequest(BaseModel):
    bank: str = "UNKNOWN"
    detected_bank: Any | None = None
    columns: list[str] = Field(default_factory=list)
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)
    current_mapping: dict[str, str | None] = Field(default_factory=dict)
    subject_account: str = ""
    subject_name: str = ""
    identity_guess: Any | None = None
    sheet_name: str = ""
    header_row: int = 0
    model: str = ""


class MappingVisionAssistRequest(MappingAssistRequest):
    file_id: str = ""


class TemplateVariantPromotionRequest(BaseModel):
    trust_state: str
    reviewer: str = "analyst"
    note: str = ""


class ProcessRequest(BaseModel):
    temp_file_path: str | None = None
    file_id: str | None = None
    bank_key: str = ""
    account: str
    name: str = ""
    confirmed_mapping: dict[str, str | None] = Field(default_factory=dict)
    operator: str = "analyst"
    header_row: int = 0
    sheet_name: str = ""


class OverrideRequest(BaseModel):
    transaction_id: str
    from_account: str | None = None
    to_account: str | None = None
    override_from_account: str | None = None
    override_to_account: str | None = None
    reason: str | None = None
    override_reason: str | None = None
    override_by: str = "analyst"
    account_number: str = ""
    account: str | None = None


class ReviewRequest(BaseModel):
    decision_value: str
    reviewer: str = "analyst"
    reviewer_note: str = ""


class TransactionCorrectionRequest(BaseModel):
    reviewer: str = "analyst"
    reason: str = ""
    changes: dict[str, Any] = Field(default_factory=dict)


class AccountCorrectionRequest(BaseModel):
    reviewer: str = "analyst"
    reason: str = ""
    changes: dict[str, Any] = Field(default_factory=dict)


class ExportRequest(BaseModel):
    export_type: str
    filters: dict[str, Any] = Field(default_factory=dict)
    created_by: str = "analyst"


class CaseTagRequest(BaseModel):
    tag: str
    description: str = ""


class CaseTagAssignRequest(BaseModel):
    case_tag_id: str
    object_type: str
    object_id: str


class DatabaseBackupRequest(BaseModel):
    operator: str = "analyst"
    note: str = ""
    backup_format: str = "json"


class DatabaseResetRequest(BaseModel):
    confirm_text: str
    operator: str = "analyst"
    note: str = ""
    create_pre_reset_backup: bool = True


class DatabaseRestoreRequest(BaseModel):
    backup_filename: str
    confirm_text: str
    operator: str = "analyst"
    note: str = ""
    create_pre_restore_backup: bool = True


class DatabaseBackupSettingsRequest(BaseModel):
    enabled: bool = False
    interval_hours: float = Field(default=24.0, ge=1.0)
    backup_format: str = "json"
    retention_enabled: bool = False
    retain_count: int = Field(default=20, ge=1)
    updated_by: str = "analyst"


class GraphNeo4jSyncRequest(BaseModel):
    include_findings: bool = True
    limit: int = Field(default=2000, ge=1, le=5000)
    filters: dict[str, Any] = Field(default_factory=dict)
