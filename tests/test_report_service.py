"""Regression tests for report scoping in services/report_service.py."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlmodel import SQLModel

from persistence.base import Base, utcnow
from persistence.models import Account, Alert, FileRecord, ParserRun, StatementBatch, Transaction
from services.report_service import generate_account_report, generate_case_report


def _make_engine(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'report-service.sqlite'}", future=True)
    Base.metadata.create_all(engine)
    SQLModel.metadata.create_all(engine)
    return engine


class FakeReport:
    """Small capture-only stand-in for FPDF-based report generation."""

    instances: list["FakeReport"] = []

    def __init__(self, report_date: str = ""):
        self.report_date = report_date
        self.info_rows: list[tuple[str, str]] = []
        self.section_titles: list[str] = []
        self.table_rows: list[list[str]] = []
        self.table_headers: list[list[str]] = []
        self.output_path: Path | None = None
        type(self).instances.append(self)

    def alias_nb_pages(self):
        return None

    def add_page(self):
        return None

    def ln(self, *_args, **_kwargs):
        return None

    def set_font(self, *_args, **_kwargs):
        return None

    def set_text_color(self, *_args, **_kwargs):
        return None

    def cell(self, *_args, **_kwargs):
        return None

    def info_row(self, label: str, value: str):
        self.info_rows.append((label, value))

    def section_title(self, title: str):
        self.section_titles.append(title)

    def table_header(self, headers: list[str], _widths: list[int]):
        self.table_headers.append(list(headers))

    def table_row(self, cells: list[str], _widths: list[int], fill: bool = False):
        del fill
        self.table_rows.append([str(cell) for cell in cells])

    def output(self, path: str):
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"%PDF-FAKE")
        self.output_path = output_path


def _make_file(file_id: str) -> FileRecord:
    return FileRecord(
        id=file_id,
        original_filename="statement.ofx",
        stored_path=f"/tmp/{file_id}.ofx",
        storage_key=f"{file_id}/original.ofx",
        file_hash_sha256=(file_id.replace("-", "") * 2)[:64].ljust(64, "0"),
        mime_type="application/x-ofx",
        file_size_bytes=128,
        uploaded_at=utcnow(),
        uploaded_by="tester",
        import_status="uploaded",
    )


def _make_run(run_id: str, file_id: str, bank_detected: str = "scb", *, finished: bool = True) -> ParserRun:
    return ParserRun(
        id=run_id,
        file_id=file_id,
        parser_version="4.0.0",
        started_at=utcnow(),
        finished_at=utcnow() if finished else None,
        status="done" if finished else "running",
        bank_detected=bank_detected,
        warning_count=0,
        error_count=0,
        summary_json={},
    )


def _make_account(
    account_id: str,
    normalized: str,
    *,
    bank_code: str,
    bank_name: str,
    holder: str,
) -> Account:
    return Account(
        id=account_id,
        bank_code=bank_code,
        bank_name=bank_name,
        normalized_account_number=normalized,
        account_holder_name=holder,
        account_type="savings",
        first_seen_at=utcnow(),
        last_seen_at=utcnow(),
        confidence_score=Decimal("1.0000"),
        source_count=1,
        status="active",
    )


def _make_statement_batch(batch_id: str, file_id: str, run_id: str, account_id: str) -> StatementBatch:
    return StatementBatch(
        id=batch_id,
        file_id=file_id,
        parser_run_id=run_id,
        account_id=account_id,
        transaction_count=1,
        overlap_status="new",
        created_at=utcnow(),
    )


def _make_transaction(
    tx_id: str,
    file_id: str,
    run_id: str,
    account_id: str,
    amount: str,
    *,
    direction: str = "OUT",
    when: datetime,
) -> Transaction:
    return Transaction(
        id=tx_id,
        file_id=file_id,
        parser_run_id=run_id,
        account_id=account_id,
        transaction_datetime=when,
        amount=Decimal(amount),
        currency="THB",
        direction=direction,
        description_raw=f"raw-{tx_id}",
        description_normalized=f"normalized-{tx_id}",
        counterparty_account_normalized=f"cp-{tx_id}",
        counterparty_name_normalized=f"Counterparty {tx_id}",
        parse_confidence=Decimal("0.9500"),
        duplicate_status="unique",
        review_status="pending",
        linkage_status="unresolved",
    )


def _make_alert(alert_id: str, account_id: str, run_id: str, summary: str) -> Alert:
    return Alert(
        id=alert_id,
        account_id=account_id,
        parser_run_id=run_id,
        rule_type="fan_out_accounts",
        severity="high",
        confidence=Decimal("0.9000"),
        finding_id=f"finding-{alert_id}",
        summary=summary,
        status="new",
        created_at=utcnow(),
    )


def test_account_report_uses_selected_parser_run_for_account_and_alert_scope(tmp_path: Path, monkeypatch):
    engine = _make_engine(tmp_path)
    monkeypatch.setattr("services.report_service.BSIEReport", FakeReport)
    monkeypatch.setattr("services.report_service.OUTPUT_DIR", tmp_path / "reports")
    FakeReport.instances.clear()

    shared_number = "1234567890"
    report_time = datetime(2024, 3, 15, 10, 0, tzinfo=timezone.utc)

    wrong_file = _make_file("11111111-1111-1111-1111-111111111111")
    target_file = _make_file("22222222-2222-2222-2222-222222222222")
    stale_file = _make_file("33333333-3333-3333-3333-333333333333")

    wrong_run = _make_run("run-wrong", wrong_file.id, "scb")
    target_run = _make_run("run-target", target_file.id, "kbank")
    stale_run = _make_run("run-stale", stale_file.id, "kbank")

    wrong_account = _make_account(
        "acct-wrong",
        shared_number,
        bank_code="scb",
        bank_name="Wrong Bank",
        holder="Wrong Holder",
    )
    target_account = _make_account(
        "acct-target",
        shared_number,
        bank_code="kbank",
        bank_name="Target Bank",
        holder="Target Holder",
    )

    target_batch = _make_statement_batch("batch-target", target_file.id, target_run.id, target_account.id)
    stale_batch = _make_statement_batch("batch-stale", stale_file.id, stale_run.id, target_account.id)

    target_tx = _make_transaction(
        "tx-target",
        target_file.id,
        target_run.id,
        target_account.id,
        "100.00",
        when=report_time,
    )
    stale_tx = _make_transaction(
        "tx-stale",
        stale_file.id,
        stale_run.id,
        target_account.id,
        "200.00",
        when=report_time.replace(day=16),
    )

    current_alert = _make_alert("alert-current", target_account.id, target_run.id, "Current run alert")
    stale_alert = _make_alert("alert-stale", target_account.id, stale_run.id, "Stale run alert")

    target_run_id = target_run.id

    with Session(engine) as session:
        session.add_all([
            wrong_file,
            target_file,
            stale_file,
            wrong_run,
            target_run,
            stale_run,
            wrong_account,
            target_account,
            target_batch,
            stale_batch,
            target_tx,
            stale_tx,
            current_alert,
            stale_alert,
        ])
        session.commit()

    with Session(engine) as session:
        pdf_path = generate_account_report(session, shared_number, parser_run_id=target_run_id, analyst="tester")

    report = FakeReport.instances[-1]
    assert pdf_path.exists()
    assert ("ชื่อเจ้าของบัญชี:", "Target Holder") in report.info_rows
    assert ("ธนาคาร:", "Target Bank") in report.info_rows
    assert any("Current run alert" in row for row in report.table_rows)
    assert all("Stale run alert" not in row for row in report.table_rows)


def test_case_report_includes_alerts_only_for_requested_accounts(tmp_path: Path, monkeypatch):
    engine = _make_engine(tmp_path)
    monkeypatch.setattr("services.report_service.BSIEReport", FakeReport)
    monkeypatch.setattr("services.report_service.OUTPUT_DIR", tmp_path / "reports")
    FakeReport.instances.clear()

    requested_file = _make_file("44444444-4444-4444-4444-444444444444")
    unrelated_file = _make_file("55555555-5555-5555-5555-555555555555")
    requested_run = _make_run("run-requested", requested_file.id, "scb")
    unrelated_run = _make_run("run-unrelated", unrelated_file.id, "kbank")

    requested_account = _make_account(
        "acct-requested",
        "1000000001",
        bank_code="scb",
        bank_name="Requested Bank",
        holder="Requested Holder",
    )
    unrelated_account = _make_account(
        "acct-unrelated",
        "2000000002",
        bank_code="kbank",
        bank_name="Unrelated Bank",
        holder="Unrelated Holder",
    )

    requested_tx = _make_transaction(
        "tx-requested",
        requested_file.id,
        requested_run.id,
        requested_account.id,
        "150.00",
        when=datetime(2024, 4, 1, 9, 0, tzinfo=timezone.utc),
    )
    unrelated_tx = _make_transaction(
        "tx-unrelated",
        unrelated_file.id,
        unrelated_run.id,
        unrelated_account.id,
        "300.00",
        when=datetime(2024, 4, 2, 9, 0, tzinfo=timezone.utc),
    )

    requested_alert = _make_alert("alert-requested", requested_account.id, requested_run.id, "Requested alert")
    unrelated_alert = _make_alert("alert-unrelated", unrelated_account.id, unrelated_run.id, "Unrelated alert")

    requested_number = requested_account.normalized_account_number

    with Session(engine) as session:
        session.add_all([
            requested_file,
            unrelated_file,
            requested_run,
            unrelated_run,
            requested_account,
            unrelated_account,
            requested_tx,
            unrelated_tx,
            requested_alert,
            unrelated_alert,
        ])
        session.commit()

    with Session(engine) as session:
        pdf_path = generate_case_report(session, [requested_number], analyst="tester")

    report = FakeReport.instances[-1]
    assert pdf_path.exists()
    assert any("Requested alert" in row for row in report.table_rows)
    assert all("Unrelated alert" not in row for row in report.table_rows)
