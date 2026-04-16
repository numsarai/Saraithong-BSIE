"""
report_service.py
-----------------
Generate investigation PDF reports using fpdf2 with TH Sarabun New font.
Produces formal reports for prosecutors and courts.
"""
from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from fpdf import FPDF
from sqlalchemy import select
from sqlalchemy.orm import Session

from paths import STATIC_DIR, OUTPUT_DIR
from persistence.models import Account, Alert, StatementBatch, Transaction

logger = logging.getLogger(__name__)

FONT_DIR = STATIC_DIR / "fonts"
FONT_REGULAR = FONT_DIR / "THSarabunNew.ttf"
FONT_BOLD = FONT_DIR / "THSarabunNew Bold.ttf"

REPORT_TITLE = "BSIE — รายงานวิเคราะห์ธุรกรรมการเงิน"
REPORT_SUBTITLE = "Bank Statement Intelligence Engine"
OWNER_NAME = "ร้อยตำรวจเอกณัฐวุฒิ สาหร่ายทอง"


def _fmt_amount(value: float | Decimal | None) -> str:
    if value is None:
        return "—"
    return f"{abs(float(value)):,.2f}"


def _fmt_date(value: Any) -> str:
    s = str(value or "")[:10]
    return s if len(s) >= 8 else "—"


def _resolve_account_for_report(
    session: Session,
    normalized_account_number: str,
    parser_run_id: str = "",
) -> Account | None:
    """Resolve the account row for a report, preferring the selected parser run."""
    if parser_run_id:
        account_row = session.scalars(
            select(Account)
            .join(StatementBatch, StatementBatch.account_id == Account.id)
            .where(
                StatementBatch.parser_run_id == parser_run_id,
                Account.normalized_account_number == normalized_account_number,
            )
            .order_by(StatementBatch.created_at.desc())
        ).first()
        if account_row:
            return account_row

        account_row = session.scalars(
            select(Account)
            .join(Transaction, Transaction.account_id == Account.id)
            .where(
                Transaction.parser_run_id == parser_run_id,
                Account.normalized_account_number == normalized_account_number,
            )
            .order_by(Transaction.transaction_datetime.asc())
        ).first()
        if account_row:
            return account_row

    return session.scalars(
        select(Account)
        .where(Account.normalized_account_number == normalized_account_number)
        .order_by(Account.last_seen_at.desc())
    ).first()


class BSIEReport(FPDF):
    """Custom FPDF subclass with TH Sarabun New font, headers, and footers."""

    def __init__(self, report_date: str = ""):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.report_date = report_date or datetime.now().strftime("%Y-%m-%d %H:%M")

        # Register TH Sarabun New
        if FONT_REGULAR.exists():
            self.add_font("THSarabun", "", str(FONT_REGULAR), uni=True)
        if FONT_BOLD.exists():
            self.add_font("THSarabun", "B", str(FONT_BOLD), uni=True)

        self.set_auto_page_break(auto=True, margin=25)

    def header(self):
        self.set_font("THSarabun", "B", 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 6, REPORT_TITLE, align="L")
        self.cell(0, 6, f"หน้า {self.page_no()}/{{nb}}", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(200, 200, 200)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-20)
        self.set_draw_color(200, 200, 200)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(2)
        self.set_font("THSarabun", "", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 5, f"จัดทำโดย: {OWNER_NAME}  |  วันที่: {self.report_date}  |  BSIE v3.0", align="C")

    def section_title(self, title: str):
        self.set_font("THSarabun", "B", 18)
        self.set_text_color(30, 41, 59)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def info_row(self, label: str, value: str):
        self.set_font("THSarabun", "B", 14)
        self.set_text_color(100, 116, 139)
        self.cell(50, 7, label, new_x="END")
        self.set_font("THSarabun", "", 14)
        self.set_text_color(15, 23, 42)
        self.cell(0, 7, value, new_x="LMARGIN", new_y="NEXT")

    def table_header(self, headers: list[str], widths: list[int]):
        self.set_font("THSarabun", "B", 12)
        self.set_fill_color(30, 41, 59)
        self.set_text_color(255, 255, 255)
        for h, w in zip(headers, widths):
            self.cell(w, 7, h, border=1, fill=True, align="C")
        self.ln()

    def table_row(self, cells: list[str], widths: list[int], fill: bool = False):
        self.set_font("THSarabun", "", 12)
        self.set_text_color(15, 23, 42)
        if fill:
            self.set_fill_color(241, 245, 249)
        for c, w in zip(cells, widths):
            self.cell(w, 6, str(c)[:30], border=1, fill=fill, align="L")
        self.ln()


def generate_account_report(
    session: Session,
    account: str,
    *,
    parser_run_id: str = "",
    analyst: str = "analyst",
) -> Path:
    """Generate a single-account investigation PDF report."""
    norm = "".join(c for c in account if c.isdigit())
    acct_row = _resolve_account_for_report(session, norm, parser_run_id)

    # Gather transaction data
    tx_query = select(Transaction).where(
        Transaction.account_id == acct_row.id if acct_row else False
    )
    if parser_run_id:
        tx_query = tx_query.where(Transaction.parser_run_id == parser_run_id)
    tx_query = tx_query.order_by(Transaction.transaction_datetime.asc())
    txns = session.scalars(tx_query).all()

    # Compute stats
    total_in = sum(abs(float(t.amount)) for t in txns if t.direction == "IN")
    total_out = sum(abs(float(t.amount)) for t in txns if t.direction == "OUT")
    dates = [str(t.posted_date or t.transaction_datetime or "")[:10] for t in txns if t.posted_date or t.transaction_datetime]
    date_range = f"{min(dates)} ถึง {max(dates)}" if dates else "—"

    # Top counterparties
    cp_map: dict[str, dict] = {}
    for t in txns:
        cp = t.counterparty_account_normalized or ""
        if not cp:
            continue
        if cp not in cp_map:
            cp_map[cp] = {"name": t.counterparty_name_normalized or "", "in": 0.0, "out": 0.0, "count": 0}
        amount = abs(float(t.amount))
        if t.direction == "IN":
            cp_map[cp]["in"] += amount
        else:
            cp_map[cp]["out"] += amount
        cp_map[cp]["count"] += 1
    top_cps = sorted(cp_map.items(), key=lambda x: -(x[1]["in"] + x[1]["out"]))[:20]

    # Alerts
    alert_query = select(Alert).where(Alert.account_id == (acct_row.id if acct_row else ""))
    if parser_run_id:
        alert_query = alert_query.where(Alert.parser_run_id == parser_run_id)
    alerts = session.scalars(alert_query.order_by(Alert.severity.asc())).all()

    # Build PDF
    pdf = BSIEReport()
    pdf.alias_nb_pages()

    # ── Cover Page ──
    pdf.add_page()
    pdf.ln(30)
    pdf.set_font("THSarabun", "B", 28)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 12, "รายงานวิเคราะห์ธุรกรรมการเงิน", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("THSarabun", "", 16)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 8, REPORT_SUBTITLE, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(20)

    pdf.info_row("เลขบัญชี:", norm)
    pdf.info_row("ชื่อเจ้าของบัญชี:", acct_row.account_holder_name if acct_row else "—")
    pdf.info_row("ธนาคาร:", acct_row.bank_name if acct_row else "—")
    pdf.info_row("ช่วงวันที่:", date_range)
    pdf.info_row("จำนวนรายการ:", f"{len(txns):,}")
    pdf.info_row("ผู้วิเคราะห์:", analyst)
    pdf.info_row("วันที่จัดทำ:", datetime.now().strftime("%d/%m/%Y %H:%M"))

    # ── Summary Stats ──
    pdf.add_page()
    pdf.section_title("สรุปภาพรวมธุรกรรม")

    stats = [
        ("ยอดรวมเงินเข้า", f"{_fmt_amount(total_in)} บาท"),
        ("ยอดรวมเงินออก", f"{_fmt_amount(total_out)} บาท"),
        ("ยอดหมุนเวียน", f"{_fmt_amount(total_in + total_out)} บาท"),
        ("จำนวนรายการทั้งหมด", f"{len(txns):,} รายการ"),
        ("จำนวนคู่สัญญา", f"{len(cp_map):,} บัญชี"),
        ("ช่วงวันที่", date_range),
    ]
    for label, value in stats:
        pdf.info_row(label, value)

    # ── Top Counterparties ──
    pdf.ln(5)
    pdf.section_title("คู่สัญญาหลัก (Top 20)")
    headers = ["ลำดับ", "เลขบัญชี", "ชื่อ", "ยอดเข้า", "ยอดออก", "รวม"]
    widths = [12, 35, 45, 30, 30, 30]
    pdf.table_header(headers, widths)
    for i, (cp_acct, data) in enumerate(top_cps):
        total = data["in"] + data["out"]
        pdf.table_row([
            str(i + 1),
            cp_acct,
            (data["name"] or "—")[:20],
            _fmt_amount(data["in"]),
            _fmt_amount(data["out"]),
            _fmt_amount(total),
        ], widths, fill=(i % 2 == 1))

    # ── Alerts ──
    if alerts:
        pdf.add_page()
        pdf.section_title(f"การแจ้งเตือน ({len(alerts)} รายการ)")
        a_headers = ["ระดับ", "กฎ", "สรุป", "สถานะ"]
        a_widths = [20, 35, 100, 25]
        pdf.table_header(a_headers, a_widths)
        for j, alert in enumerate(alerts):
            pdf.table_row([
                alert.severity,
                alert.rule_type,
                (alert.summary or "—")[:50],
                alert.status,
            ], a_widths, fill=(j % 2 == 1))

    # ── Transaction Sample ──
    pdf.add_page()
    pdf.section_title("ตัวอย่างรายการธุรกรรม (50 รายการยอดสูงสุด)")
    top_txns = sorted(txns, key=lambda t: abs(float(t.amount)), reverse=True)[:50]
    t_headers = ["วันที่", "จำนวนเงิน", "ทิศทาง", "คู่สัญญา", "รายละเอียด"]
    t_widths = [25, 30, 15, 40, 70]
    pdf.table_header(t_headers, t_widths)
    for k, txn in enumerate(top_txns):
        pdf.table_row([
            _fmt_date(txn.posted_date or txn.transaction_datetime),
            _fmt_amount(txn.amount),
            txn.direction or "—",
            (txn.counterparty_name_normalized or txn.counterparty_account_normalized or "—")[:18],
            (txn.description_normalized or "—")[:35],
        ], t_widths, fill=(k % 2 == 1))

    # ── Signature Block ──
    pdf.add_page()
    pdf.ln(30)
    pdf.section_title("ลงนาม")
    pdf.ln(20)

    for title_line in ["ผู้วิเคราะห์ / ผู้จัดทำรายงาน", "ผู้ตรวจสอบ / ผู้บังคับบัญชา"]:
        pdf.set_font("THSarabun", "", 14)
        pdf.cell(0, 8, "ลงชื่อ ............................................................", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"(                                                        )", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("THSarabun", "B", 14)
        pdf.cell(0, 8, title_line, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"วันที่ ......./......./.........", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(15)

    # Save
    output_dir = OUTPUT_DIR / norm
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"report_{norm}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf.output(str(pdf_path))
    logger.info("PDF report generated: %s", pdf_path)
    return pdf_path


def generate_case_report(
    session: Session,
    accounts: list[str],
    *,
    analyst: str = "analyst",
) -> Path:
    """Generate a multi-account case investigation PDF report."""
    pdf = BSIEReport()
    pdf.alias_nb_pages()

    # Cover
    pdf.add_page()
    pdf.ln(30)
    pdf.set_font("THSarabun", "B", 28)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 12, "รายงานสรุปคดี — วิเคราะห์ธุรกรรมการเงิน", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("THSarabun", "", 16)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 8, REPORT_SUBTITLE, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(20)

    pdf.info_row("จำนวนบัญชี:", f"{len(accounts)} บัญชี")
    pdf.info_row("ผู้วิเคราะห์:", analyst)
    pdf.info_row("วันที่จัดทำ:", datetime.now().strftime("%d/%m/%Y %H:%M"))

    # Per-account summaries
    requested_account_ids: set[str] = set()
    for acct_num in accounts:
        norm = "".join(c for c in acct_num if c.isdigit())
        if not norm:
            continue

        acct_row = _resolve_account_for_report(session, norm)
        if not acct_row:
            continue
        requested_account_ids.add(acct_row.id)

        txns = session.scalars(
            select(Transaction).where(Transaction.account_id == acct_row.id)
        ).all()

        total_in = sum(abs(float(t.amount)) for t in txns if t.direction == "IN")
        total_out = sum(abs(float(t.amount)) for t in txns if t.direction == "OUT")

        pdf.add_page()
        pdf.section_title(f"บัญชี: {norm}")
        pdf.info_row("ชื่อ:", acct_row.account_holder_name or "—")
        pdf.info_row("ธนาคาร:", acct_row.bank_name or "—")
        pdf.info_row("ยอดเข้า:", f"{_fmt_amount(total_in)} บาท")
        pdf.info_row("ยอดออก:", f"{_fmt_amount(total_out)} บาท")
        pdf.info_row("รายการ:", f"{len(txns):,}")

    # Combined alerts
    all_alerts = []
    if requested_account_ids:
        all_alerts = session.scalars(
            select(Alert)
            .where(Alert.account_id.in_(requested_account_ids))
            .order_by(Alert.severity.asc())
        ).all()
    if all_alerts:
        pdf.add_page()
        pdf.section_title(f"การแจ้งเตือนทั้งหมด ({len(all_alerts)} รายการ)")
        a_headers = ["ระดับ", "กฎ", "สรุป", "สถานะ"]
        a_widths = [20, 35, 100, 25]
        pdf.table_header(a_headers, a_widths)
        for j, alert in enumerate(all_alerts[:50]):
            pdf.table_row([
                alert.severity,
                alert.rule_type,
                (alert.summary or "—")[:50],
                alert.status,
            ], a_widths, fill=(j % 2 == 1))

    # Signature
    pdf.add_page()
    pdf.ln(30)
    pdf.section_title("ลงนาม")
    pdf.ln(20)
    for title_line in ["ผู้วิเคราะห์ / ผู้จัดทำรายงาน", "ผู้ตรวจสอบ / ผู้บังคับบัญชา"]:
        pdf.set_font("THSarabun", "", 14)
        pdf.cell(0, 8, "ลงชื่อ ............................................................", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"(                                                        )", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("THSarabun", "B", 14)
        pdf.cell(0, 8, title_line, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"วันที่ ......./......./.........", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(15)

    # Save
    pdf_path = OUTPUT_DIR / f"case_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf.output(str(pdf_path))
    logger.info("Case PDF report generated: %s", pdf_path)
    return pdf_path
