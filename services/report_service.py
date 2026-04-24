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
from services.copilot_service import (
    CopilotNotFoundError,
    CopilotScopeError,
    answer_copilot_question,
)

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


def _safe_text(value: Any, *, limit: int = 2000) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else f"{text[: limit - 3]}..."


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

    def paragraph(self, text: str, *, size: int = 13):
        self.set_font("THSarabun", "", size)
        self.set_text_color(15, 23, 42)
        self.multi_cell(0, 6, str(text or "—"))
        self.ln(2)


async def build_account_report_llm_analysis(
    session: Session,
    account: str,
    *,
    parser_run_id: str = "",
    analyst: str = "analyst",
    model: str = "",
    max_transactions: int = 30,
) -> dict[str, Any]:
    """Build a read-only local LLM analysis payload for the account report."""
    norm = "".join(c for c in account if c.isdigit())
    scope = {
        "parser_run_id": str(parser_run_id or ""),
        "file_id": "",
        "account": norm,
        "case_tag_id": "",
        "case_tag": "",
    }
    question = (
        "จัดทำบทวิเคราะห์สำหรับใส่ในรายงานการสอบสวนจากหลักฐานที่กำหนดเท่านั้น "
        "ให้ระบุภาพรวมธุรกรรม คู่สัญญาสำคัญ สัญญาณเตือนหรือรูปแบบที่ควรตรวจสอบ "
        "ข้อจำกัดของข้อมูล และรายการที่ควรตรวจสอบต่อ โดยต้องอ้างอิง evidence id ทุกข้อเท็จจริง"
    )

    try:
        result = await answer_copilot_question(
            session,
            question=question,
            scope=scope,
            operator=analyst,
            model=model,
            max_transactions=max_transactions,
            task_mode="investigation_report_analysis",
        )
        return {
            "enabled": True,
            "status": result.get("status", "ok"),
            "source": result.get("source", "local_llm_investigation_copilot"),
            "model": result.get("model", model or "local-default"),
            "task_mode": result.get("task_mode", "investigation_report_analysis"),
            "answer": _safe_text(result.get("answer"), limit=3600),
            "scope": result.get("scope", scope),
            "context_hash": result.get("context_hash", ""),
            "citation_policy": result.get("citation_policy", {}),
            "citations": list(result.get("citations") or [])[:20],
            "warnings": list(result.get("warnings") or []),
            "audit_id": result.get("audit_id", ""),
        }
    except (CopilotNotFoundError, CopilotScopeError, ConnectionError, RuntimeError, ValueError) as exc:
        return {
            "enabled": True,
            "status": "unavailable",
            "source": "local_llm_report_analysis",
            "model": model or "local-default",
            "task_mode": "investigation_report_analysis",
            "answer": "ไม่สามารถสร้างบทวิเคราะห์จาก Local LLM ได้ในรอบนี้ รายงานส่วนอื่นยังสร้างจากข้อมูลธุรกรรมและการแจ้งเตือนที่ตรวจสอบได้ตามปกติ",
            "scope": scope,
            "context_hash": "",
            "citation_policy": {"status": "unavailable", "requires_review": True, "warning": str(exc)[:300]},
            "citations": [],
            "warnings": [str(exc)[:300]],
            "audit_id": "",
        }


async def build_case_report_llm_analysis(
    session: Session,
    accounts: list[str],
    *,
    analyst: str = "analyst",
    model: str = "",
    max_accounts: int = 3,
    max_transactions: int = 20,
) -> dict[str, Any]:
    """Build a bounded local LLM analysis payload for a multi-account case report."""
    clean_accounts = ["".join(c for c in str(account or "") if c.isdigit()) for account in accounts]
    clean_accounts = [account for account in clean_accounts if account]
    if not clean_accounts:
        return {
            "enabled": True,
            "status": "unavailable",
            "source": "local_llm_report_analysis",
            "model": model or "local-default",
            "task_mode": "investigation_report_analysis",
            "answer": "ไม่สามารถสร้างบทวิเคราะห์จาก Local LLM ได้ เนื่องจากไม่พบเลขบัญชีที่ใช้เป็นขอบเขตหลักฐาน",
            "scope": {"accounts": []},
            "context_hash": "",
            "citation_policy": {"status": "unavailable", "requires_review": True, "warning": "no account scope"},
            "citations": [],
            "warnings": ["no account scope"],
            "audit_id": "",
        }

    analyses: list[dict[str, Any]] = []
    for account in clean_accounts[:max_accounts]:
        analyses.append(
            await build_account_report_llm_analysis(
                session,
                account,
                analyst=analyst,
                model=model,
                max_transactions=max_transactions,
            )
        )

    answer_parts = []
    citations: list[dict[str, Any]] = []
    warnings = [
        "บทวิเคราะห์ Local LLM สำหรับรายงานหลายบัญชีนี้เป็นการวิเคราะห์รายบัญชี ไม่ใช่ข้อสรุป cross-account ขั้นสุดท้าย"
    ]
    for account, analysis in zip(clean_accounts[:max_accounts], analyses):
        answer_parts.append(f"บัญชี {account}: {_safe_text(analysis.get('answer'), limit=1800)}")
        citations.extend(list(analysis.get("citations") or []))
        warnings.extend(str(item) for item in (analysis.get("warnings") or []) if str(item).strip())

    if len(clean_accounts) > max_accounts:
        warnings.append(f"จำกัดบทวิเคราะห์ LLM ไว้ที่ {max_accounts} บัญชีแรกจากทั้งหมด {len(clean_accounts)} บัญชี")

    statuses = {str(item.get("status") or "") for item in analyses}
    status = "ok" if statuses == {"ok"} else "needs_review" if analyses else "unavailable"
    return {
        "enabled": True,
        "status": status,
        "source": "local_llm_case_report_analysis",
        "model": analyses[0].get("model") if analyses else (model or "local-default"),
        "task_mode": "investigation_report_analysis",
        "answer": "\n\n".join(answer_parts),
        "scope": {"accounts": clean_accounts[:max_accounts], "account_count": len(clean_accounts)},
        "context_hash": "",
        "citation_policy": {"status": status, "requires_review": status != "ok", "warning": ""},
        "citations": citations[:20],
        "warnings": warnings[:12],
        "audit_id": "",
    }


def _add_llm_analysis_section(pdf: BSIEReport, llm_analysis: dict[str, Any] | None):
    if not llm_analysis:
        return

    pdf.add_page()
    pdf.section_title("บทวิเคราะห์จาก Local LLM")
    pdf.info_row("สถานะ:", str(llm_analysis.get("status") or "—"))
    pdf.info_row("โมเดล:", str(llm_analysis.get("model") or "—"))
    if llm_analysis.get("audit_id"):
        pdf.info_row("Audit ID:", str(llm_analysis.get("audit_id")))
    if llm_analysis.get("context_hash"):
        pdf.info_row("Context Hash:", str(llm_analysis.get("context_hash"))[:16])

    pdf.paragraph(
        "หมายเหตุ: ส่วนนี้เป็นร่างบทวิเคราะห์จาก Local LLM โดยใช้เฉพาะหลักฐานที่อยู่ในขอบเขตรายงานนี้ "
        "ไม่ใช่ข้อสรุปสุดท้ายทางคดีหรือข้อวินิจฉัยทางกฎหมาย ผู้วิเคราะห์ต้องตรวจสอบกับรายการต้นฉบับและพยานหลักฐานประกอบอีกครั้ง"
    )
    pdf.paragraph(_safe_text(llm_analysis.get("answer"), limit=3600))

    warnings = [str(item) for item in (llm_analysis.get("warnings") or []) if str(item).strip()]
    if warnings:
        pdf.section_title("ข้อควรตรวจสอบจาก LLM")
        for warning in warnings[:5]:
            pdf.paragraph(f"- {_safe_text(warning, limit=300)}", size=12)

    citations = list(llm_analysis.get("citations") or [])[:12]
    if citations:
        pdf.section_title("หลักฐานที่ LLM อ้างอิง")
        headers = ["Citation", "ประเภท", "รายละเอียด"]
        widths = [42, 25, 110]
        pdf.table_header(headers, widths)
        for i, item in enumerate(citations):
            pdf.table_row([
                item.get("id", "—"),
                item.get("type", "—"),
                item.get("label", item.get("object_id", "—")),
            ], widths, fill=(i % 2 == 1))


def generate_account_report(
    session: Session,
    account: str,
    *,
    parser_run_id: str = "",
    analyst: str = "analyst",
    llm_analysis: dict[str, Any] | None = None,
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

    _add_llm_analysis_section(pdf, llm_analysis)

    # ── Top Counterparties ──
    pdf.add_page()
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
    llm_analysis: dict[str, Any] | None = None,
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

    _add_llm_analysis_section(pdf, llm_analysis)

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
