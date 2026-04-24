"""
LLM Service — Local LLM integration via Ollama with RAG from database.

Uses RAG pattern: loads project context from config/llm_context.md,
auto-queries the database for relevant transactions, then sends to LLM.
All processing stays on-premise — no data leaves the machine.
"""

import base64
import json
import logging
import os as _os
import re
import struct
import time
import zlib
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
    _os.getenv("OLLAMA_TEXT_MODEL", _os.getenv("OLLAMA_DEFAULT_MODEL", "qwen3.5:9b")).strip()
    or "qwen3.5:9b"
)
DEFAULT_VISION_MODEL = _os.getenv("OLLAMA_VISION_MODEL", "gemma4:e4b").strip() or "gemma4:e4b"
DEFAULT_FAST_MODEL = _os.getenv("OLLAMA_FAST_MODEL", "gemma4:e4b").strip() or "gemma4:e4b"
DEFAULT_MODEL = _os.getenv("OLLAMA_DEFAULT_MODEL", DEFAULT_TEXT_MODEL).strip() or DEFAULT_TEXT_MODEL
REQUEST_TIMEOUT = float(_os.getenv("OLLAMA_TIMEOUT", "120.0"))

_MODEL_ROLE_DEFAULTS = {
    "default": DEFAULT_MODEL,
    "text": DEFAULT_TEXT_MODEL,
    "vision": DEFAULT_VISION_MODEL,
    "fast": DEFAULT_FAST_MODEL,
}
_BENCHMARK_ROLES = {"text", "fast", "vision"}
_BENCHMARK_MAX_TOKENS = 512
_BENCHMARK_PROMPT = (
    "Local BSIE model benchmark. Do not use real case data. "
    "Do not think step by step. "
    "Return exactly this compact JSON object and stop. "
    "No markdown, no explanation, no extra keys: "
    "{\"status\":\"ok\",\"language\":\"th\",\"fields\":[\"date\",\"amount\",\"description\"]}"
)


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def _tiny_png_bytes() -> bytes:
    # 1x1 white RGB PNG generated with valid chunk CRCs for vision-model smoke tests.
    header = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw_scanline = b"\x00\xff\xff\xff"
    return header + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", zlib.compress(raw_scanline)) + _png_chunk(b"IEND", b"")


_BENCHMARK_IMAGE_BYTES = _tiny_png_bytes()


def _ollama_root_url() -> str:
    root = OLLAMA_BASE_URL.rstrip("/")
    if root.endswith("/v1"):
        root = root[:-3].rstrip("/")
    return root or "http://localhost:11434"


def _ollama_api_url(path: str) -> str:
    return f"{_ollama_root_url()}/{path.lstrip('/')}"


def _ollama_openai_url(path: str) -> str:
    return f"{_ollama_root_url()}/v1/{path.lstrip('/')}"


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


def _json_object_ok(text: str) -> bool:
    content = str(text or "").strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        content = fence_match.group(1).strip()
    elif "{" in content and "}" in content:
        content = content[content.find("{"):content.rfind("}") + 1]
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return False
    return isinstance(parsed, dict)


def _benchmark_roles(roles: list[str] | None, *, include_vision: bool) -> list[str]:
    if roles:
        selected = [str(role or "").strip().lower() for role in roles]
    else:
        selected = ["text", "fast"]
        if include_vision:
            selected.append("vision")

    result: list[str] = []
    for role in selected:
        if role not in _BENCHMARK_ROLES:
            raise ValueError(f"Unsupported benchmark role: {role}")
        if role not in result:
            result.append(role)
    return result


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
            resp = await client.get(_ollama_api_url("/api/tags"))
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


async def benchmark_llm_roles(
    *,
    roles: list[str] | None = None,
    iterations: int = 1,
    include_vision: bool = False,
    model_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run a tiny local-only benchmark against configured Ollama model roles."""
    selected_roles = _benchmark_roles(roles, include_vision=include_vision)
    count = max(1, min(5, int(iterations or 1)))
    overrides = {
        str(role or "").strip().lower(): str(model or "").strip()
        for role, model in (model_overrides or {}).items()
        if str(model or "").strip()
    }
    config = get_llm_model_config()
    role_results: list[dict[str, Any]] = []

    for role in selected_roles:
        selected_model = resolve_model(overrides.get(role, ""), role)
        runs: list[dict[str, Any]] = []
        for index in range(count):
            started = time.perf_counter()
            try:
                if role == "vision":
                    response = await chat_with_file(
                        _BENCHMARK_PROMPT,
                        _BENCHMARK_IMAGE_BYTES,
                        "image/png",
                        model=selected_model,
                        max_tokens=_BENCHMARK_MAX_TOKENS,
                        think=False,
                    )
                else:
                    response = await chat(
                        _BENCHMARK_PROMPT,
                        auto_context=False,
                        model=selected_model,
                        max_tokens=_BENCHMARK_MAX_TOKENS,
                        think=False,
                    )
                elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
                text = str(response.get("response", "") or "")
                json_ok = _json_object_ok(text)
                runs.append({
                    "iteration": index + 1,
                    "status": "ok" if json_ok else "invalid_json",
                    "duration_ms": elapsed_ms,
                    "json_ok": json_ok,
                    "prompt_tokens": int(response.get("prompt_tokens", 0) or 0),
                    "completion_tokens": int(response.get("completion_tokens", 0) or 0),
                    "response_preview": text[:240],
                })
            except ConnectionError as exc:
                elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
                runs.append({
                    "iteration": index + 1,
                    "status": "offline",
                    "duration_ms": elapsed_ms,
                    "json_ok": False,
                    "error": str(exc),
                })
            except RuntimeError as exc:
                elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
                runs.append({
                    "iteration": index + 1,
                    "status": "error",
                    "duration_ms": elapsed_ms,
                    "json_ok": False,
                    "error": str(exc),
                })
            except httpx.TimeoutException as exc:
                elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
                runs.append({
                    "iteration": index + 1,
                    "status": "timeout",
                    "duration_ms": elapsed_ms,
                    "json_ok": False,
                    "error": str(exc) or "Ollama request timed out",
                })

        durations = [float(run["duration_ms"]) for run in runs]
        ok_runs = [run for run in runs if run["status"] == "ok"]
        if len(ok_runs) == len(runs):
            role_status = "ok"
        elif all(run["status"] == "offline" for run in runs):
            role_status = "offline"
        else:
            role_status = "partial"

        role_results.append({
            "role": role,
            "model": selected_model,
            "status": role_status,
            "iterations": count,
            "ok_count": len(ok_runs),
            "average_duration_ms": round(sum(durations) / len(durations), 2) if durations else 0,
            "runs": runs,
        })

    if all(item["status"] == "ok" for item in role_results):
        status = "ok"
    elif all(item["status"] == "offline" for item in role_results):
        status = "offline"
    else:
        status = "partial"

    return {
        "status": status,
        "source": "local_llm_benchmark",
        "local_only": True,
        "iterations": count,
        "model_roles": config["roles"],
        "results": role_results,
    }


async def chat(
    message: str,
    *,
    account: str = "",
    transactions: list[dict[str, Any]] | None = None,
    auto_context: bool = True,
    model: str = "",
    max_tokens: int | None = None,
    think: bool | None = None,
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
    if max_tokens is not None:
        payload["max_tokens"] = max(1, int(max_tokens))
    if think is not None:
        native_payload: dict[str, Any] = {
            "model": selected_model,
            "messages": payload["messages"],
            "stream": False,
            "think": bool(think),
        }
        if max_tokens is not None:
            native_payload["options"] = {"num_predict": max(1, int(max_tokens))}
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.post(_ollama_api_url("/api/chat"), json=native_payload)
                resp.raise_for_status()
                data = resp.json()

            message_data = data.get("message", {})
            return {
                "response": message_data.get("content", ""),
                "model": data.get("model", selected_model),
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
            }
        except httpx.ConnectError:
            raise ConnectionError(
                "ไม่สามารถเชื่อมต่อ Ollama ได้ — กรุณาตรวจสอบว่า Ollama กำลังทำงานอยู่ (ollama serve)"
            )
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"Ollama error: {exc.response.status_code} — {exc.response.text}")

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(_ollama_openai_url("/chat/completions"), json=payload)
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
    max_tokens: int | None = None,
    think: bool | None = None,
) -> dict[str, Any]:
    """
    Send an image/PDF file to the LLM for multimodal analysis.
    The configured vision model must support image inputs.

    Args:
        message: User's question about the file.
        file_bytes: Raw file bytes (image or first page rendered as image).
        file_type: MIME type (image/png, image/jpeg, etc.)
        model: Ollama model name.
        think: Whether to enable model reasoning when supported by Ollama.
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
    if max_tokens is not None:
        payload["max_tokens"] = max(1, int(max_tokens))
    if think is not None:
        native_payload: dict[str, Any] = {
            "model": selected_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": message
                    or "วิเคราะห์เอกสารนี้ สรุปข้อมูลที่พบ รวมถึงยอดเงิน ชื่อบัญชี และรูปแบบที่น่าสงสัย (ถ้ามี)",
                    "images": [b64_data],
                },
            ],
            "stream": False,
            "think": bool(think),
        }
        if max_tokens is not None:
            native_payload["options"] = {"num_predict": max(1, int(max_tokens))}
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.post(_ollama_api_url("/api/chat"), json=native_payload)
                resp.raise_for_status()
                data = resp.json()

            message_data = data.get("message", {})
            return {
                "response": message_data.get("content", ""),
                "model": data.get("model", selected_model),
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
            }
        except httpx.ConnectError:
            raise ConnectionError("ไม่สามารถเชื่อมต่อ Ollama ได้ — กรุณารัน ollama serve")
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"Ollama error: {exc.response.status_code} — {exc.response.text}")

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(_ollama_openai_url("/chat/completions"), json=payload)
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
