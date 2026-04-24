from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Awaitable, Callable

from sqlalchemy import and_, case, desc, func, or_, select
from sqlalchemy.orm import Session

from persistence.models import Account, Alert, AuditLog, FileRecord, ParserRun, ReviewDecision, Transaction
from services.audit_service import log_audit
from services.llm_service import chat, resolve_model


class CopilotScopeError(ValueError):
    """Raised when a copilot scope is missing or internally inconsistent."""


class CopilotNotFoundError(LookupError):
    """Raised when a requested scope object does not exist."""


_ACCOUNT_DIGIT_RE = re.compile(r"\D+")
_CITATION_RE = re.compile(r"\[(?:txn|alert|run|file|account):[A-Za-z0-9_.:\-]+\]")
_INSUFFICIENT_RE = re.compile(r"(หลักฐานไม่พอ|หลักฐานไม่เพียงพอ|insufficient|not enough evidence)", re.I)
_COPILOT_MAX_TOKENS = 900
_COPILOT_TASKS: dict[str, dict[str, Any]] = {
    "freeform": {
        "label": "Freeform evidence question",
        "default_question": "",
        "instructions": [
            "Answer the analyst question directly from the deterministic context pack.",
            "Separate confirmed evidence from uncertainty.",
        ],
    },
    "account_summary": {
        "label": "Account summary",
        "default_question": "Summarize this scoped account, parser run, or file evidence.",
        "instructions": [
            "Summarize transaction count, total incoming, total outgoing, net flow, date range, key counterparties, and notable alerts when present.",
            "Cite account/run/file ids for scope-level claims and transaction/alert ids for record-level claims.",
            "Do not infer account ownership or intent beyond the context pack.",
        ],
    },
    "alert_explanation": {
        "label": "Alert explanation",
        "default_question": "Explain the alerts in this scoped evidence.",
        "instructions": [
            "Explain each alert's rule type, severity, confidence, and why the pattern matters for review.",
            "Cite alert ids and supporting transaction ids when available.",
            "If no alert rows are present, say หลักฐานไม่พอ for alert explanation and state which scoped alert evidence is missing.",
        ],
    },
    "review_checklist": {
        "label": "Review checklist",
        "default_question": "Create an analyst review checklist for this scoped evidence.",
        "instructions": [
            "Return a concise checklist of review actions grounded in the context pack.",
            "Separate items already supported by evidence from items requiring analyst review.",
            "Do not mark anything final, confirmed, resolved, classified, or promoted.",
        ],
    },
    "draft_report_paragraph": {
        "label": "Draft report paragraph",
        "default_question": "Draft a report paragraph from this scoped evidence.",
        "instructions": [
            "Draft one court-ready paragraph in cautious language.",
            "Every factual claim must include citations.",
            "Make clear it is a draft based only on the scoped evidence, not a final investigative conclusion.",
        ],
    },
}


ChatCallable = Callable[..., Awaitable[dict[str, Any]]]


def _normalize_task_mode(task_mode: str | None) -> str:
    clean = str(task_mode or "freeform").strip() or "freeform"
    if clean not in _COPILOT_TASKS:
        allowed = ", ".join(sorted(_COPILOT_TASKS))
        raise CopilotScopeError(f"unsupported copilot task_mode: {clean}; allowed: {allowed}")
    return clean


def _iso(value: Any) -> str | None:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return None


def _as_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _digits(value: str) -> str:
    return _ACCOUNT_DIGIT_RE.sub("", str(value or ""))


def _stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _short_hash(value: str | None) -> str:
    return str(value or "")[:12]


def _scope_identity(scope: dict[str, Any]) -> dict[str, str]:
    parser_run_id = str(scope.get("parser_run_id") or "").strip()
    file_id = str(scope.get("file_id") or "").strip()
    account = str(scope.get("account") or "").strip()
    account_digits = _digits(account)
    if not any([parser_run_id, file_id, account_digits]):
        raise CopilotScopeError("copilot_scope requires parser_run_id, file_id, or account")
    return {
        "parser_run_id": parser_run_id,
        "file_id": file_id,
        "account": account,
        "account_digits": account_digits,
    }


def _citation(citation_type: str, object_id: str, label: str, **extra: Any) -> dict[str, Any]:
    return {
        "id": f"{citation_type}:{object_id}",
        "type": citation_type,
        "object_id": object_id,
        "label": label,
        **{key: value for key, value in extra.items() if value not in (None, "")},
    }


def _transaction_dict(row: Transaction) -> dict[str, Any]:
    return {
        "citation_id": f"txn:{row.id}",
        "transaction_id": row.id,
        "datetime": _iso(row.transaction_datetime),
        "posted_date": _iso(row.posted_date),
        "amount": _as_float(row.amount),
        "currency": row.currency,
        "direction": row.direction,
        "balance_after": _as_float(row.balance_after) if row.balance_after is not None else None,
        "description": row.description_raw or row.description_normalized or "",
        "transaction_type": row.transaction_type or "",
        "counterparty_account": row.counterparty_account_normalized or row.counterparty_account_raw or "",
        "counterparty_name": row.counterparty_name_normalized or row.counterparty_name_raw or "",
        "source_row_id": row.source_row_id or "",
        "review_status": row.review_status,
        "linkage_status": row.linkage_status,
    }


def _alert_dict(row: Alert) -> dict[str, Any]:
    return {
        "citation_id": f"alert:{row.id}",
        "alert_id": row.id,
        "rule_type": row.rule_type,
        "severity": row.severity,
        "confidence": _as_float(row.confidence),
        "summary": row.summary or "",
        "status": row.status,
        "finding_id": row.finding_id or "",
        "transaction_id": row.transaction_id or "",
        "created_at": _iso(row.created_at),
    }


def _preview_value(value: Any, *, limit: int = 240) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    else:
        text = str(value)
    return text if len(text) <= limit else f"{text[: limit - 3]}..."


def _related_citation_id(object_type: str, object_id: str) -> str:
    citation_type_by_object = {
        "transaction": "txn",
        "account": "account",
        "file": "file",
        "parser_run": "run",
        "alert": "alert",
    }
    citation_type = citation_type_by_object.get(object_type)
    return f"{citation_type}:{object_id}" if citation_type else ""


def _object_scope_filter(model: Any, object_ids_by_type: dict[str, list[str]]) -> Any:
    filters = [
        and_(model.object_type == object_type, model.object_id.in_(sorted(set(object_ids))))
        for object_type, object_ids in object_ids_by_type.items()
        if object_ids
    ]
    if not filters:
        return model.object_id == "__no_review_scope__"
    return or_(*filters)


def _review_decision_dict(row: ReviewDecision) -> dict[str, Any]:
    return {
        "review_decision_id": row.id,
        "object_type": row.object_type,
        "object_id": row.object_id,
        "citation_id": _related_citation_id(row.object_type, row.object_id),
        "decision_type": row.decision_type,
        "decision_value": row.decision_value,
        "reviewer": row.reviewer,
        "reviewer_note": row.reviewer_note or "",
        "created_at": _iso(row.created_at),
    }


def _audit_event_dict(row: AuditLog) -> dict[str, Any]:
    return {
        "audit_id": row.id,
        "object_type": row.object_type,
        "object_id": row.object_id,
        "citation_id": _related_citation_id(row.object_type, row.object_id),
        "action_type": row.action_type,
        "field_name": row.field_name or "",
        "changed_by": row.changed_by,
        "changed_at": _iso(row.changed_at),
        "reason": row.reason or "",
        "old_value": _preview_value(row.old_value_json),
        "new_value": _preview_value(row.new_value_json),
    }


def build_copilot_context_pack(
    session: Session,
    scope: dict[str, Any],
    *,
    max_transactions: int = 20,
) -> dict[str, Any]:
    """Build a deterministic, read-only evidence pack for copilot prompts."""
    scope_ids = _scope_identity(scope)
    limit = max(1, min(50, int(max_transactions or 20)))
    warnings: list[str] = []
    citations: list[dict[str, Any]] = []

    parser_run: ParserRun | None = None
    file_row: FileRecord | None = None
    account_rows: list[Account] = []

    if scope_ids["parser_run_id"]:
        parser_run = session.get(ParserRun, scope_ids["parser_run_id"])
        if parser_run is None:
            raise CopilotNotFoundError(f"parser_run_id not found: {scope_ids['parser_run_id']}")
        citations.append(_citation("run", parser_run.id, "parser run", status=parser_run.status))

    effective_file_id = scope_ids["file_id"] or (parser_run.file_id if parser_run else "")
    if effective_file_id:
        file_row = session.get(FileRecord, effective_file_id)
        if file_row is None:
            raise CopilotNotFoundError(f"file_id not found: {effective_file_id}")
        if parser_run and scope_ids["file_id"] and parser_run.file_id != scope_ids["file_id"]:
            raise CopilotScopeError("parser_run_id does not belong to file_id")
        citations.append(_citation("file", file_row.id, file_row.original_filename))

    if scope_ids["account_digits"]:
        account_rows = list(
            session.scalars(
                select(Account)
                .where(Account.normalized_account_number == scope_ids["account_digits"])
                .order_by(Account.last_seen_at.desc())
            )
        )
        if account_rows:
            for row in account_rows:
                citations.append(
                    _citation(
                        "account",
                        row.id,
                        row.display_account_number or row.normalized_account_number or row.id,
                        bank=row.bank_code or row.bank_name or "",
                    )
                )
        else:
            warnings.append("selected account was not found in the account registry")

    conditions = []
    if parser_run:
        conditions.append(Transaction.parser_run_id == parser_run.id)
    elif file_row:
        conditions.append(Transaction.file_id == file_row.id)
    if account_rows:
        conditions.append(Transaction.account_id.in_([row.id for row in account_rows]))
    elif scope_ids["account_digits"]:
        conditions.append(Transaction.id == "__no_account_match__")

    if not conditions:
        raise CopilotScopeError("copilot_scope did not resolve to a transaction filter")

    in_amount = case((Transaction.direction == "IN", func.abs(Transaction.amount)), else_=0)
    out_amount = case((Transaction.direction == "OUT", func.abs(Transaction.amount)), else_=0)
    summary_row = session.execute(
        select(
            func.count(Transaction.id),
            func.sum(in_amount),
            func.sum(out_amount),
            func.min(Transaction.transaction_datetime),
            func.max(Transaction.transaction_datetime),
        ).where(*conditions)
    ).one()

    transaction_count = int(summary_row[0] or 0)
    total_in = _as_float(summary_row[1])
    total_out = _as_float(summary_row[2])
    if transaction_count == 0:
        warnings.append("no transactions matched the current copilot scope")

    transaction_rows = list(
        session.scalars(
            select(Transaction)
            .where(*conditions)
            .order_by(desc(func.abs(Transaction.amount)), Transaction.transaction_datetime.desc())
            .limit(limit)
        )
    )
    transactions = [_transaction_dict(row) for row in transaction_rows]
    citations.extend(
        _citation("txn", row.id, f"{row.direction} {_as_float(row.amount):,.2f} THB")
        for row in transaction_rows
    )

    total_expr = func.sum(func.abs(Transaction.amount))
    counterparty_rows = session.execute(
        select(
            Transaction.counterparty_account_normalized,
            Transaction.counterparty_name_normalized,
            Transaction.direction,
            total_expr.label("total_amount"),
            func.count(Transaction.id).label("transaction_count"),
        )
        .where(
            *conditions,
            Transaction.counterparty_account_normalized.isnot(None),
            Transaction.counterparty_account_normalized != "",
        )
        .group_by(
            Transaction.counterparty_account_normalized,
            Transaction.counterparty_name_normalized,
            Transaction.direction,
        )
        .order_by(desc(total_expr))
        .limit(10)
    ).all()
    counterparties = [
        {
            "counterparty_account": row.counterparty_account_normalized,
            "counterparty_name": row.counterparty_name_normalized or "",
            "direction": row.direction,
            "total_amount": _as_float(row.total_amount),
            "transaction_count": int(row.transaction_count or 0),
        }
        for row in counterparty_rows
    ]

    alert_conditions = []
    if parser_run:
        alert_conditions.append(Alert.parser_run_id == parser_run.id)
    elif file_row:
        run_ids = list(
            session.scalars(select(ParserRun.id).where(ParserRun.file_id == file_row.id))
        )
        if run_ids:
            alert_conditions.append(Alert.parser_run_id.in_(run_ids))
        else:
            alert_conditions.append(Alert.id == "__no_parser_run_match__")
    if account_rows:
        alert_conditions.append(Alert.account_id.in_([row.id for row in account_rows]))
    elif scope_ids["account_digits"]:
        alert_conditions.append(Alert.id == "__no_account_match__")

    alert_rows: list[Alert] = []
    if alert_conditions:
        alert_rows = list(
            session.scalars(
                select(Alert)
                .where(*alert_conditions)
                .order_by(Alert.created_at.desc())
                .limit(10)
            )
        )
    alerts = [_alert_dict(row) for row in alert_rows]
    citations.extend(_citation("alert", row.id, row.rule_type, severity=row.severity) for row in alert_rows)

    review_scope: dict[str, list[str]] = {}
    if file_row:
        review_scope.setdefault("file", []).append(file_row.id)
    if parser_run:
        review_scope.setdefault("parser_run", []).append(parser_run.id)
    if account_rows:
        review_scope["account"] = [row.id for row in account_rows]
    if transaction_rows:
        review_scope["transaction"] = [row.id for row in transaction_rows]
    if alert_rows:
        review_scope["alert"] = [row.id for row in alert_rows]

    review_decision_rows = list(
        session.scalars(
            select(ReviewDecision)
            .where(_object_scope_filter(ReviewDecision, review_scope))
            .order_by(ReviewDecision.created_at.desc())
            .limit(20)
        )
    )
    audit_rows = list(
        session.scalars(
            select(AuditLog)
            .where(
                _object_scope_filter(AuditLog, review_scope),
                AuditLog.object_type != "llm_copilot",
            )
            .order_by(AuditLog.changed_at.desc())
            .limit(20)
        )
    )
    review_history = {
        "scope_note": "review/audit history is limited to scoped accounts, alerts, file/run rows, and included top transactions",
        "decision_count": len(review_decision_rows),
        "audit_event_count": len(audit_rows),
        "review_decisions": [_review_decision_dict(row) for row in review_decision_rows],
        "audit_events": [_audit_event_dict(row) for row in audit_rows],
    }

    accounts = [
        {
            "citation_id": f"account:{row.id}",
            "account_id": row.id,
            "bank_code": row.bank_code or "",
            "bank_name": row.bank_name or "",
            "display_account_number": row.display_account_number or "",
            "normalized_account_number": row.normalized_account_number or "",
            "account_holder_name": row.account_holder_name or "",
            "status": row.status,
        }
        for row in account_rows
    ]

    evidence = {
        "file": {
            "citation_id": f"file:{file_row.id}" if file_row else "",
            "file_id": file_row.id if file_row else "",
            "original_filename": file_row.original_filename if file_row else "",
            "sha256_prefix": _short_hash(file_row.file_hash_sha256 if file_row else ""),
            "bank_detected": file_row.bank_detected if file_row else "",
            "import_status": file_row.import_status if file_row else "",
        },
        "parser_run": {
            "citation_id": f"run:{parser_run.id}" if parser_run else "",
            "parser_run_id": parser_run.id if parser_run else "",
            "status": parser_run.status if parser_run else "",
            "bank_detected": parser_run.bank_detected if parser_run else "",
            "warning_count": parser_run.warning_count if parser_run else 0,
            "error_count": parser_run.error_count if parser_run else 0,
        },
        "accounts": accounts,
        "summary": {
            "transaction_count": transaction_count,
            "total_in": total_in,
            "total_out": total_out,
            "net_flow": total_in - total_out,
            "date_from": _iso(summary_row[3]),
            "date_to": _iso(summary_row[4]),
            "alert_count": len(alerts),
        },
        "top_transactions": transactions,
        "top_counterparties": counterparties,
        "alerts": alerts,
        "review_history": review_history,
    }
    pack_without_hash = {
        "source": "deterministic_copilot_context",
        "read_only": True,
        "mutations_allowed": False,
        "scope": scope_ids,
        "evidence": evidence,
        "citations": citations,
        "warnings": warnings,
        "limits": {"max_transactions": limit, "max_alerts": 10, "max_counterparties": 10},
    }
    context_hash = _stable_hash(pack_without_hash)
    return {
        **pack_without_hash,
        "context_hash": context_hash,
    }


def build_copilot_prompt(question: str, context_pack: dict[str, Any], *, task_mode: str = "freeform") -> str:
    """Create the LLM prompt from deterministic context only."""
    task_mode_id = _normalize_task_mode(task_mode)
    task = _COPILOT_TASKS[task_mode_id]
    task_instructions = "\n".join(f"- {item}" for item in task["instructions"])
    compact_context = json.dumps(context_pack, ensure_ascii=False, sort_keys=True, default=str)
    return (
        "You are BSIE Investigation Copilot for Thai police financial analysis.\n"
        "Answer in Thai unless the analyst explicitly asks otherwise.\n"
        "Use only the deterministic context pack below. Do not use outside knowledge, guesses, or hidden database context.\n"
        "Every factual claim must cite at least one evidence id exactly like [txn:<id>], [alert:<id>], [run:<id>], [file:<id>], or [account:<id>].\n"
        "When discussing review_history or audit_events, cite the underlying record id from each event's citation_id field.\n"
        "If the context pack does not contain enough evidence, say หลักฐานไม่พอ and explain what scoped evidence is missing.\n"
        "Do not mutate evidence, classify transactions, promote mappings, change alerts, or issue final investigative findings.\n\n"
        f"Task mode: {task_mode_id}\n"
        f"Task label: {task['label']}\n"
        f"Task instructions:\n{task_instructions}\n\n"
        f"Analyst focus/question:\n{question.strip()}\n\n"
        f"Deterministic context pack:\n{compact_context}"
    )


def _citation_policy(answer: str) -> dict[str, Any]:
    if _CITATION_RE.search(answer):
        return {"status": "ok", "requires_review": False, "warning": ""}
    if _INSUFFICIENT_RE.search(answer):
        return {"status": "insufficient_evidence", "requires_review": False, "warning": ""}
    return {
        "status": "missing_citation",
        "requires_review": True,
        "warning": "LLM response did not include required evidence citations or an insufficient-evidence statement.",
    }


async def answer_copilot_question(
    session: Session,
    *,
    question: str,
    scope: dict[str, Any],
    operator: str = "analyst",
    model: str = "",
    max_transactions: int = 20,
    task_mode: str = "freeform",
    llm_chat: ChatCallable = chat,
) -> dict[str, Any]:
    """Answer a scoped investigation question without mutating evidence."""
    task_mode_id = _normalize_task_mode(task_mode)
    clean_question = str(question or "").strip()
    if not clean_question and task_mode_id == "freeform":
        raise CopilotScopeError("question is required")
    if not clean_question:
        clean_question = _COPILOT_TASKS[task_mode_id]["default_question"]

    context_pack = build_copilot_context_pack(session, scope, max_transactions=max_transactions)
    prompt = build_copilot_prompt(clean_question, context_pack, task_mode=task_mode_id)
    prompt_hash = _stable_hash({"prompt": prompt})
    selected_model = resolve_model(model, "text")
    audit_row: AuditLog = log_audit(
        session,
        object_type="llm_copilot",
        object_id=context_pack["context_hash"],
        action_type="copilot_requested",
        changed_by=operator,
        field_name="answer",
        old_value=None,
        new_value={"status": "requested"},
        reason="investigation copilot read-only scoped answer",
        extra_context={
            "scope": context_pack["scope"],
            "context_hash": context_pack["context_hash"],
            "prompt_hash": prompt_hash,
            "model": selected_model,
            "task_mode": task_mode_id,
            "task_label": _COPILOT_TASKS[task_mode_id]["label"],
            "question": clean_question[:500],
            "read_only": True,
            "mutations_allowed": False,
        },
    )
    try:
        response = await llm_chat(
            prompt,
            auto_context=False,
            model=selected_model,
            max_tokens=_COPILOT_MAX_TOKENS,
            think=False,
        )
    except Exception as exc:
        audit_row.action_type = "copilot_failed"
        audit_row.new_value_json = {
            "status": "error",
            "error": str(exc)[:500],
        }
        session.flush()
        raise

    answer = str(response.get("response") or "").strip()
    policy = _citation_policy(answer)
    warnings = list(context_pack.get("warnings") or [])
    if policy["warning"]:
        warnings.append(policy["warning"])

    result = {
        "status": "ok" if not policy["requires_review"] else "needs_review",
        "source": "local_llm_investigation_copilot",
        "read_only": True,
        "mutations_allowed": False,
        "model": response.get("model") or selected_model,
        "task_mode": task_mode_id,
        "answer": answer,
        "scope": context_pack["scope"],
        "context_hash": context_pack["context_hash"],
        "prompt_hash": prompt_hash,
        "citation_policy": policy,
        "citations": context_pack["citations"],
        "warnings": warnings,
        "audit_id": audit_row.id,
        "usage": {
            "prompt_tokens": int(response.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(response.get("completion_tokens", 0) or 0),
        },
    }
    audit_row.action_type = "copilot_answered"
    audit_row.new_value_json = {
        "status": result["status"],
        "task_mode": task_mode_id,
        "citation_policy": policy["status"],
        "answer_preview": answer[:500],
    }
    session.flush()
    return result
