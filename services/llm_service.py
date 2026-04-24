"""
LLM Service — Local LLM integration via Ollama with RAG from database.

Uses RAG pattern: loads project context from config/llm_context.md,
auto-queries the database for relevant transactions, then sends to LLM.
All processing stays on-premise — no data leaves the machine.
"""

import base64
import logging
import os as _os
import re
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import func, select, or_

from persistence.base import get_db_session
from persistence.models import Account, Transaction

logger = logging.getLogger("bsie.llm")

_BASE_DIR = Path(__file__).resolve().parent.parent
_CONTEXT_FILE = _BASE_DIR / "config" / "llm_context.md"

OLLAMA_BASE_URL = (
    _os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()
    or "http://localhost:11434"
)
DEFAULT_TEXT_MODEL = (
    _os.getenv("OLLAMA_TEXT_MODEL", _os.getenv("OLLAMA_DEFAULT_MODEL", "qwen2.5:14b")).strip()
    or "qwen2.5:14b"
)
DEFAULT_VISION_MODEL = _os.getenv("OLLAMA_VISION_MODEL", "qwen2.5vl:7b").strip() or "qwen2.5vl:7b"
DEFAULT_FAST_MODEL = _os.getenv("OLLAMA_FAST_MODEL", "gemma4:e4b").strip() or "gemma4:e4b"
DEFAULT_MODEL = _os.getenv("OLLAMA_DEFAULT_MODEL", DEFAULT_TEXT_MODEL).strip() or DEFAULT_TEXT_MODEL
REQUEST_TIMEOUT = float(_os.getenv("OLLAMA_TIMEOUT", "120.0"))

_MODEL_ROLE_DEFAULTS = {
    "default": DEFAULT_MODEL,
    "text": DEFAULT_TEXT_MODEL,
    "vision": DEFAULT_VISION_MODEL,
    "fast": DEFAULT_FAST_MODEL,
}


def resolve_model(model: str | None = "", role: str = "default") -> str:
    """Return an explicit model or the configured default for the requested role."""
    explicit = str(model or "").strip()
    if explicit:
        return explicit
    role_key = str(role or "default").strip().lower()
    return _MODEL_ROLE_DEFAULTS.get(role_key, DEFAULT_MODEL)


def get_llm_model_config() -> dict[str, Any]:
    """Expose non-secret local LLM runtime defaults for status/debug UI."""
    return {
        "base_url": OLLAMA_BASE_URL,
        "timeout_seconds": REQUEST_TIMEOUT,
        "default_model": DEFAULT_MODEL,
        "roles": dict(_MODEL_ROLE_DEFAULTS),
    }


def _load_system_prompt() -> str:
    """Load project context markdown as the system prompt."""
    if _CONTEXT_FILE.exists():
        return _CONTEXT_FILE.read_text(encoding="utf-8")
    return "คุณเป็นผู้ช่วยวิเคราะห์ทางการเงินของระบบ BSIE"


# ── Database Query Helpers ────────────────────────────────────────────────

_LIKE_ESCAPE_RE = re.compile(r"[%_\\]")
_MAX_SEARCH_LEN = 100


def _safe_like(value: str) -> str:
    """Escape LIKE wildcards and limit length to prevent DoS."""
    return _LIKE_ESCAPE_RE.sub(lambda m: f"\\{m.group()}", value.strip()[:_MAX_SEARCH_LEN])


def _resolve_account_id(session: Any, account_number: str) -> str | None:
    """Resolve account number to account ID."""
    safe = _safe_like(account_number)
    row = session.scalars(
        select(Account).where(
            or_(
                Account.normalized_account_number == account_number,
                Account.normalized_account_number.like(f"%{safe}%"),
            )
        )
    ).first()
    return str(row.id) if row else None


def get_account_summary(account_number: str) -> dict[str, Any]:
    """Get account summary stats from the database."""
    with get_db_session() as session:
        account_id = _resolve_account_id(session, account_number)
        if not account_id:
            return {"found": False, "account": account_number}

        # Get account info
        acct = session.scalars(
            select(Account).where(Account.id == account_id)
        ).first()

        # Transaction count
        txn_count = session.scalar(
            select(func.count(Transaction.id))
            .where(Transaction.account_id == account_id)
        ) or 0

        # Total in/out
        total_in = float(session.scalar(
            select(func.sum(func.abs(Transaction.amount)))
            .where(Transaction.account_id == account_id, Transaction.direction == "IN")
        ) or 0)
        total_out = float(session.scalar(
            select(func.sum(func.abs(Transaction.amount)))
            .where(Transaction.account_id == account_id, Transaction.direction == "OUT")
        ) or 0)

        # Date range
        min_date = session.scalar(
            select(func.min(Transaction.transaction_datetime))
            .where(Transaction.account_id == account_id)
        )
        max_date = session.scalar(
            select(func.max(Transaction.transaction_datetime))
            .where(Transaction.account_id == account_id)
        )

        # Unique counterparties
        cp_count = session.scalar(
            select(func.count(func.distinct(Transaction.counterparty_account_normalized)))
            .where(
                Transaction.account_id == account_id,
                Transaction.counterparty_account_normalized.isnot(None),
            )
        ) or 0

        # Top counterparties by total amount
        top_cps = session.execute(
            select(
                Transaction.counterparty_account_normalized,
                Transaction.counterparty_name_normalized,
                Transaction.direction,
                func.sum(func.abs(Transaction.amount)).label("total"),
                func.count().label("cnt"),
            )
            .where(
                Transaction.account_id == account_id,
                Transaction.counterparty_account_normalized.isnot(None),
            )
            .group_by(
                Transaction.counterparty_account_normalized,
                Transaction.counterparty_name_normalized,
                Transaction.direction,
            )
            .order_by(func.sum(func.abs(Transaction.amount)).desc())
            .limit(10)
        ).all()

        top_counterparties = []
        for row in top_cps:
            top_counterparties.append({
                "account": row.counterparty_account_normalized,
                "name": row.counterparty_name_normalized or "",
                "direction": row.direction,
                "total": float(row.total),
                "count": int(row.cnt),
            })

        return {
            "found": True,
            "account": account_number,
            "holder_name": acct.account_holder_name if acct else "",
            "bank": acct.bank_name if acct else "",
            "transaction_count": txn_count,
            "total_in": total_in,
            "total_out": total_out,
            "net_flow": total_in - total_out,
            "date_range": f"{min_date} ~ {max_date}" if min_date else "N/A",
            "unique_counterparties": cp_count,
            "top_counterparties": top_counterparties,
        }


def get_account_transactions(account_number: str, *, limit: int = 50) -> list[dict[str, Any]]:
    """Get recent transactions for an account from the database."""
    with get_db_session() as session:
        account_id = _resolve_account_id(session, account_number)
        if not account_id:
            return []

        txns = session.scalars(
            select(Transaction)
            .where(Transaction.account_id == account_id)
            .order_by(Transaction.transaction_datetime.desc())
            .limit(limit)
        ).all()

        return [
            {
                "transaction_datetime": str(t.transaction_datetime or ""),
                "amount": float(t.amount) if t.amount else 0,
                "direction": t.direction or "",
                "counterparty_account": t.counterparty_account_normalized or "",
                "counterparty_name": t.counterparty_name_normalized or "",
                "transaction_type": t.transaction_type or "",
                "description": t.description_normalized or t.description_raw or "",
                "balance": float(t.balance) if t.balance else None,
                "duplicate_status": t.duplicate_status or "",
                "review_status": t.review_status or "",
            }
            for t in txns
        ]


def get_all_accounts_summary() -> list[dict[str, Any]]:
    """Get a summary list of all accounts in the database (single query)."""
    from sqlalchemy import case

    with get_db_session() as session:
        rows = session.execute(
            select(
                Account.normalized_account_number,
                Account.account_holder_name,
                Account.bank_name,
                func.count(Transaction.id).label("txn_count"),
                func.coalesce(
                    func.sum(case((Transaction.direction == "IN", func.abs(Transaction.amount)), else_=0)), 0
                ).label("total_in"),
                func.coalesce(
                    func.sum(case((Transaction.direction == "OUT", func.abs(Transaction.amount)), else_=0)), 0
                ).label("total_out"),
            )
            .outerjoin(Transaction, Transaction.account_id == Account.id)
            .group_by(Account.id)
            .order_by(Account.first_seen_at.desc())
        ).all()

        return [
            {
                "account": row.normalized_account_number or "",
                "holder_name": row.account_holder_name or "",
                "bank": row.bank_name or "",
                "transaction_count": int(row.txn_count),
                "total_in": float(row.total_in),
                "total_out": float(row.total_out),
            }
            for row in rows
        ]


def search_transactions(query: str, *, limit: int = 30) -> list[dict[str, Any]]:
    """Search transactions by keyword across descriptions, counterparty names, etc."""
    with get_db_session() as session:
        like = f"%{_safe_like(query)}%"
        txns = session.scalars(
            select(Transaction)
            .join(Account, Transaction.account_id == Account.id, isouter=True)
            .where(
                or_(
                    Transaction.description_normalized.like(like),
                    Transaction.counterparty_name_normalized.like(like),
                    Transaction.counterparty_account_normalized.like(like),
                    Transaction.reference_no.like(like),
                    Account.normalized_account_number.like(like),
                )
            )
            .order_by(Transaction.transaction_datetime.desc())
            .limit(limit)
        ).all()

        return [
            {
                "transaction_datetime": str(t.transaction_datetime or ""),
                "amount": float(t.amount) if t.amount else 0,
                "direction": t.direction or "",
                "counterparty_account": t.counterparty_account_normalized or "",
                "counterparty_name": t.counterparty_name_normalized or "",
                "transaction_type": t.transaction_type or "",
                "description": t.description_normalized or t.description_raw or "",
            }
            for t in txns
        ]


# ── Formatting Helpers ───────────────────────────────────────────────────

def _format_transactions(transactions: list[dict[str, Any]], limit: int = 50) -> str:
    """Format transaction rows into readable text for the LLM."""
    if not transactions:
        return "(ไม่มีข้อมูลธุรกรรม)"

    lines: list[str] = []
    for i, txn in enumerate(transactions[:limit]):
        date = txn.get("transaction_datetime") or txn.get("posted_date") or txn.get("date", "?")
        amount = txn.get("amount", 0)
        direction = txn.get("direction", "?")
        cp_name = txn.get("counterparty_name") or txn.get("counterparty_name_normalized", "?")
        cp_acct = txn.get("counterparty_account") or txn.get("counterparty_account_normalized", "?")
        desc = txn.get("description") or txn.get("description_normalized") or txn.get("description_raw", "")
        txn_type = txn.get("transaction_type", "")

        lines.append(
            f"{i + 1}. [{date}] {direction} {amount:,.2f} บาท "
            f"| คู่สัญญา: {cp_name} ({cp_acct}) "
            f"| ประเภท: {txn_type} | {desc}"
        )

    text = "\n".join(lines)
    if len(transactions) > limit:
        text += f"\n... (แสดง {limit} จาก {len(transactions)} รายการ)"
    return text


def _format_account_summary(summary: dict[str, Any]) -> str:
    """Format account summary dict into readable text."""
    if not summary.get("found"):
        return f"ไม่พบบัญชี {summary.get('account', '?')} ในฐานข้อมูล"

    lines = [
        f"บัญชี: {summary['account']}",
        f"ชื่อ: {summary.get('holder_name', '—')}",
        f"ธนาคาร: {summary.get('bank', '—')}",
        f"จำนวนธุรกรรม: {summary['transaction_count']:,}",
        f"ยอดรวมเข้า: {summary['total_in']:,.2f} บาท",
        f"ยอดรวมออก: {summary['total_out']:,.2f} บาท",
        f"เงินไหลสุทธิ: {summary['net_flow']:,.2f} บาท",
        f"ช่วงวันที่: {summary['date_range']}",
        f"คู่สัญญาทั้งหมด: {summary['unique_counterparties']} ราย",
    ]

    if summary.get("top_counterparties"):
        lines.append("\nคู่สัญญาหลัก (Top 10):")
        for cp in summary["top_counterparties"]:
            lines.append(
                f"  - {cp['name'] or cp['account']} ({cp['account']}) "
                f"| {cp['direction']} {cp['total']:,.2f} บาท ({cp['count']} รายการ)"
            )

    return "\n".join(lines)


def _format_all_accounts(accounts: list[dict[str, Any]]) -> str:
    """Format all accounts summary for context."""
    if not accounts:
        return "(ไม่มีบัญชีในฐานข้อมูล)"

    lines = [f"บัญชีทั้งหมดในฐานข้อมูล ({len(accounts)} บัญชี):"]
    for a in accounts:
        lines.append(
            f"  - {a['account']} | {a['holder_name']} | {a['bank']} "
            f"| {a['transaction_count']:,} รายการ "
            f"| เข้า {a['total_in']:,.0f} | ออก {a['total_out']:,.0f}"
        )
    return "\n".join(lines)


# ── Ollama API ───────────────────────────────────────────────────────────

async def check_ollama_status() -> dict[str, Any]:
    """Check if Ollama is running and which models are available."""
    config = get_llm_model_config()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = [m["name"] for m in data.get("models", [])]
            return {
                "status": "ok",
                "models": models,
                "model_roles": config["roles"],
                "llm_config": config,
            }
    except Exception as exc:
        return {
            "status": "offline",
            "error": str(exc),
            "models": [],
            "model_roles": config["roles"],
            "llm_config": config,
        }


async def chat(
    message: str,
    *,
    account: str = "",
    transactions: list[dict[str, Any]] | None = None,
    auto_context: bool = True,
    model: str = "",
) -> dict[str, Any]:
    """
    Send a chat message to the local LLM with project context.

    When auto_context=True (default), automatically queries the database
    for relevant account data if an account number is mentioned.
    """
    system_prompt = _load_system_prompt()

    # Build context from database
    parts: list[str] = []

    if auto_context:
        import asyncio

        # If account is specified, pull its data from DB (in thread to avoid blocking)
        if account:
            summary = await asyncio.to_thread(get_account_summary, account)
            parts.append("=== ข้อมูลบัญชีจากฐานข้อมูล ===")
            parts.append(_format_account_summary(summary))

            if not transactions and summary.get("found"):
                db_txns = await asyncio.to_thread(get_account_transactions, account, limit=50)
                if db_txns:
                    parts.append(f"\n=== ธุรกรรมล่าสุด ({len(db_txns)} รายการ) ===")
                    parts.append(_format_transactions(db_txns))
        else:
            all_accounts = await asyncio.to_thread(get_all_accounts_summary)
            active = [a for a in all_accounts if a["transaction_count"] > 0]
            top = sorted(active, key=lambda a: a["transaction_count"], reverse=True)[:20]
            if top:
                parts.append(f"=== ข้อมูลบัญชีในฐานข้อมูล ({len(active)} บัญชีที่มีธุรกรรม, แสดง top 20) ===")
                parts.append(_format_all_accounts(top))

    # If transactions were explicitly provided, include them
    if transactions:
        parts.append(f"\n=== ธุรกรรมที่ระบุ ({len(transactions)} รายการ) ===")
        parts.append(_format_transactions(transactions))

    parts.append(f"\nคำถาม: {message}")
    user_content = "\n".join(parts)
    selected_model = resolve_model(model, "text")

    payload = {
        "model": selected_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(f"{OLLAMA_BASE_URL}/v1/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()

        choice = data.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "")
        usage = data.get("usage", {})

        return {
            "response": content,
            "model": data.get("model", selected_model),
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
        }
    except httpx.ConnectError:
        raise ConnectionError(
            "ไม่สามารถเชื่อมต่อ Ollama ได้ — กรุณาตรวจสอบว่า Ollama กำลังทำงานอยู่ (ollama serve)"
        )
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"Ollama error: {exc.response.status_code} — {exc.response.text}")


async def summarize_account(
    account: str,
    model: str = "",
) -> dict[str, Any]:
    """Summarize an account by pulling all data from the database."""
    message = (
        "สรุปภาพรวมบัญชีนี้ให้กระชับ ครอบคลุม:\n"
        "1. ข้อมูลพื้นฐาน (ชื่อ ธนาคาร ช่วงวันที่)\n"
        "2. ยอดรวมเข้า-ออก จำนวนรายการ\n"
        "3. คู่สัญญาหลัก (top 5 ที่มียอดสูงสุด)\n"
        "4. รูปแบบที่น่าสงสัย (ถ้ามี) พร้อมระบุระดับความเชื่อมั่น\n"
        "5. ข้อเสนอแนะสำหรับพนักงานสอบสวน"
    )
    return await chat(message, account=account, model=model)


async def classify_transaction(
    transaction: dict[str, Any],
    model: str = "",
) -> dict[str, Any]:
    """Classify a single transaction — normal, suspicious, or needs review."""
    message = (
        "จำแนกธุรกรรมนี้เป็น 1 ใน 3 ประเภท:\n"
        "- NORMAL: ธุรกรรมปกติ\n"
        "- SUSPICIOUS: น่าสงสัย (ระบุเหตุผล)\n"
        "- REVIEW: ต้องตรวจสอบเพิ่มเติม\n"
        "ตอบเป็น JSON: {\"classification\": \"...\", \"reason\": \"...\", \"confidence\": \"สูง/กลาง/ต่ำ\"}"
    )
    return await chat(message, transactions=[transaction], auto_context=False, model=model)


async def chat_with_file(
    message: str,
    file_bytes: bytes,
    file_type: str,
    *,
    model: str = "",
) -> dict[str, Any]:
    """
    Send an image/PDF file to the LLM for multimodal analysis.
    The configured vision model must support image inputs.

    Args:
        message: User's question about the file.
        file_bytes: Raw file bytes (image or first page rendered as image).
        file_type: MIME type (image/png, image/jpeg, etc.)
        model: Ollama model name.
    """
    system_prompt = _load_system_prompt()
    b64_data = base64.b64encode(file_bytes).decode("utf-8")
    selected_model = resolve_model(model, "vision")

    # Ollama's OpenAI-compatible API with image content
    payload = {
        "model": selected_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{file_type};base64,{b64_data}"},
                    },
                    {
                        "type": "text",
                        "text": message or "วิเคราะห์เอกสารนี้ สรุปข้อมูลที่พบ รวมถึงยอดเงิน ชื่อบัญชี และรูปแบบที่น่าสงสัย (ถ้ามี)",
                    },
                ],
            },
        ],
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(f"{OLLAMA_BASE_URL}/v1/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()

        choice = data.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "")
        usage = data.get("usage", {})

        return {
            "response": content,
            "model": data.get("model", selected_model),
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
        }
    except httpx.ConnectError:
        raise ConnectionError("ไม่สามารถเชื่อมต่อ Ollama ได้ — กรุณารัน ollama serve")
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"Ollama error: {exc.response.status_code} — {exc.response.text}")
