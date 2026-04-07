"""
graph_export.py
---------------
Deterministic graph export helpers for BSIE.

Produces:
- nodes.csv
- nodes.json
- edges.csv
- edges.json
- aggregated_edges.csv
- aggregated_edges.json
- derived_account_edges.csv
- derived_account_edges.json
- graph_manifest.json

Design goals:
- stable typed node IDs
- stable edge IDs
- explicit review/assertion status
- lineage preserved in every edge record
- downstream-friendly `id/source/target/type/label` columns
- consistent graph schema for both legacy package exports and DB-backed export jobs
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from core.graph_domain import DERIVED_ACCOUNT_EDGE_COLUMNS
from utils.date_utils import format_date_range
from utils.text_utils import normalize_text


GRAPH_NODE_COLUMNS = [
    "id",
    "node_id",
    "label",
    "type",
    "node_type",
    "identity_value",
    "account_number",
    "partial_account",
    "entity_name",
    "bank_name",
    "transaction_id",
    "statement_batch_id",
    "review_status",
    "confidence_score",
    "source_count",
    "first_seen",
    "last_seen",
    "source_transaction_ids",
    "file_ids",
    "parser_run_ids",
    "statement_batch_ids",
    "source_row_numbers",
    "source_sheets",
    "source_files",
    "lineage_json",
]

GRAPH_EDGE_COLUMNS = [
    "id",
    "edge_id",
    "source",
    "from_node_id",
    "target",
    "to_node_id",
    "label",
    "type",
    "edge_type",
    "aggregation_level",
    "directionality",
    "amount",
    "amount_display",
    "currency",
    "date",
    "time",
    "transaction_count",
    "confidence_score",
    "review_status",
    "assertion_status",
    "duplicate_status",
    "transaction_id",
    "source_transaction_ids",
    "statement_batch_id",
    "parser_run_id",
    "file_id",
    "source_row_number",
    "source_sheet",
    "source_file",
    "reference_no",
    "description",
    "lineage_json",
]

AGGREGATED_EDGE_COLUMNS = [
    "id",
    "edge_id",
    "source",
    "from_node_id",
    "target",
    "to_node_id",
    "label",
    "type",
    "edge_type",
    "aggregation_level",
    "directionality",
    "transaction_count",
    "total_amount_signed",
    "total_amount_abs",
    "total_amount_display",
    "currency",
    "date_range",
    "confidence_score_avg",
    "confidence_score_min",
    "confidence_score_max",
    "review_status",
    "assertion_status",
    "source_transaction_ids",
    "statement_batch_id",
    "parser_run_id",
    "file_id",
    "source_row_numbers",
    "source_sheets",
    "source_files",
    "lineage_json",
]

SUPPORTED_NODE_TYPES = [
    "Account",
    "PartialAccount",
    "Entity",
    "Bank",
    "StatementBatch",
    "Transaction",
    "Cash",
    "Unknown",
]

SUPPORTED_EDGE_TYPES = [
    "OWNS",
    "SENT_TO",
    "RECEIVED_FROM",
    "DERIVED_ACCOUNT_TO_ACCOUNT",
    "MATCHED_TO",
    "POSSIBLE_SAME_AS",
    "APPEARS_IN",
]

GENERIC_UNKNOWN_LABEL = "Unknown Counterparty"

GRAPH_EXPORT_JSON_FILENAMES = {
    "nodes": "nodes.json",
    "edges": "edges.json",
    "aggregated_edges": "aggregated_edges.json",
    "derived_account_edges": "derived_account_edges.json",
}


def _json_text(value: Any) -> str:
    if value in ("", None):
        return ""
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return json.dumps(parsed, ensure_ascii=False, sort_keys=True, default=str)
        except Exception:
            return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _json_dict(value: Any) -> dict[str, Any]:
    if not value:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _stable_join(values: Iterable[object]) -> str:
    prepared = sorted({str(value).strip() for value in values if str(value or "").strip()})
    return "|".join(prepared)


def _split_pipe(value: object) -> set[str]:
    if value in ("", None):
        return set()
    if isinstance(value, str):
        return {part.strip() for part in value.split("|") if part.strip()}
    return {str(value).strip()}


def _hash_id(prefix: str, *parts: object) -> str:
    raw = "|".join(str(part or "") for part in parts)
    # nosemgrep: python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1 -- This is used only for stable graph/export identifiers, not for cryptographic integrity.
    return f"{prefix}:{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16].upper()}"


def _clean_account(value: object) -> str:
    text = str(value or "").strip()
    if text.startswith("PARTIAL:"):
        text = text[len("PARTIAL:"):]
    return "".join(ch for ch in text if ch.isdigit())


def _extract_partial_account(raw_value: object, normalized_value: object = "") -> str:
    if _clean_account(normalized_value):
        return ""
    digits = _clean_account(raw_value)
    return digits if 1 <= len(digits) < 10 else ""


def _is_full_account(value: object) -> bool:
    digits = _clean_account(value)
    return len(digits) in {10, 12}


def _is_partial_account(value: object) -> bool:
    digits = _clean_account(value)
    return 1 <= len(digits) < 10


def _node_id_for_account(value: object) -> str:
    return f"ACCOUNT:{_clean_account(value)}"


def _node_id_for_partial(value: object) -> str:
    return f"PARTIAL_ACCOUNT:{_clean_account(value)}"


def _node_id_for_bank(bank_name: str) -> str:
    normalized = normalize_text(bank_name or "").lower()
    if not normalized:
        normalized = "unknown"
    return f"BANK:{normalized.replace(' ', '_')}"


def _node_id_for_entity(name: str) -> str:
    normalized = normalize_text(name or "").lower()
    return _hash_id("ENTITY", normalized or "unknown")


def _node_id_for_batch(batch_id: str, account_number: str, bank_name: str, dates: Iterable[str]) -> str:
    if batch_id:
        return f"STATEMENT_BATCH:{batch_id}"
    return _hash_id(
        "STATEMENT_BATCH",
        account_number,
        bank_name,
        "|".join(sorted({str(date or "") for date in dates if str(date or "").strip()})),
    )


def _node_id_for_transaction(transaction_key: str) -> str:
    return f"TRANSACTION:{transaction_key}"


def _float_or_zero(value: object) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _string_or_blank(value: object) -> str:
    return str(value or "").strip()


def _format_money_display(value: object) -> str:
    amount = abs(_float_or_zero(value))
    if amount == 0 and str(value or "").strip() in {"", "None", "nan"}:
        return ""
    if float(amount).is_integer():
        return f"{int(amount):,}"
    return f"{amount:,.2f}"


def _format_date_display(value: object) -> str:
    text = _string_or_blank(value)
    if not text:
        return ""
    for splitter in ("T", " "):
        if splitter in text:
            text = text.split(splitter, 1)[0]
            break
    parts = text.split("-")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        return f"{parts[2]} {parts[1]} {parts[0]}"
    parts = text.split("/")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        if len(parts[2]) == 4:
            return f"{parts[0].zfill(2)} {parts[1].zfill(2)} {parts[2]}"
    return text


def _human_account_label(account_number: str, name: str = "") -> str:
    account_number = _string_or_blank(account_number)
    normalized_name = normalize_text(name or "")
    if account_number and normalized_name and normalized_name != account_number:
        return f"{normalized_name} ({account_number})"
    return normalized_name or account_number or GENERIC_UNKNOWN_LABEL


def _extract_lineage(row: pd.Series) -> dict[str, Any]:
    lineage = _json_dict(row.get("lineage_json"))
    row_number = _string_or_blank(row.get("row_number", "") or row.get("source_row_number", ""))
    if row_number:
        lineage["source_row_number"] = row_number
    source_sheet = _string_or_blank(row.get("source_sheet", "") or row.get("sheet_name", "") or lineage.get("sheet"))
    if source_sheet:
        lineage["sheet"] = source_sheet
    source_file = _string_or_blank(row.get("source_file", "") or lineage.get("source_file"))
    if source_file:
        lineage["source_file"] = source_file

    for field in (
        "file_id",
        "parser_run_id",
        "statement_batch_id",
        "reference_no",
        "transaction_fingerprint",
        "transaction_record_id",
        "db_transaction_id",
        "subject_account",
        "subject_name",
        "bank",
        "duplicate_status",
        "review_status",
        "source_row_id",
    ):
        value = _string_or_blank(row.get(field, "") or lineage.get(field))
        if value:
            lineage[field] = value

    if _string_or_blank(row.get("bank", "")) and not lineage.get("bank_detected"):
        lineage["bank_detected"] = _string_or_blank(row.get("bank", ""))

    return lineage


def _stable_transaction_key(row: pd.Series) -> str:
    lineage = _extract_lineage(row)
    file_identity = _string_or_blank(lineage.get("file_id") or lineage.get("source_file"))
    source_row_number = _string_or_blank(lineage.get("source_row_number"))
    tx_fingerprint = _string_or_blank(row.get("transaction_fingerprint") or lineage.get("transaction_fingerprint"))
    explicit_id = _string_or_blank(
        row.get("transaction_record_id")
        or row.get("transaction_id")
        or lineage.get("transaction_record_id")
        or lineage.get("transaction_id")
    )

    if file_identity and source_row_number:
        return _hash_id("TX", file_identity, source_row_number, tx_fingerprint or explicit_id or row.get("amount", ""))
    if explicit_id and tx_fingerprint:
        return _hash_id("TX", explicit_id, tx_fingerprint)
    if explicit_id:
        return _hash_id("TX", explicit_id)
    if tx_fingerprint:
        return _hash_id("TX", tx_fingerprint)
    return _hash_id(
        "TX",
        row.get("date", ""),
        row.get("time", ""),
        row.get("amount", ""),
        row.get("description", ""),
        row.get("reference_no", ""),
    )


def _transaction_label(row: pd.Series, transaction_key: str) -> str:
    explicit_id = _string_or_blank(row.get("transaction_record_id") or row.get("transaction_id"))
    if explicit_id:
        return explicit_id
    reference_no = _string_or_blank(row.get("reference_no", ""))
    if reference_no:
        return f"REF {reference_no}"
    date_value = _string_or_blank(row.get("date", ""))
    amount = _float_or_zero(row.get("amount"))
    currency = _string_or_blank(row.get("currency", "THB")) or "THB"
    if date_value:
        return f"{date_value} {abs(amount):,.2f} {currency}"
    return transaction_key


def _transaction_aliases(row: pd.Series, transaction_key: str) -> set[str]:
    lineage = _extract_lineage(row)
    aliases = {
        transaction_key,
        _string_or_blank(row.get("db_transaction_id", "")),
        _string_or_blank(row.get("id", "")),
        _string_or_blank(row.get("transaction_id", "")),
        _string_or_blank(row.get("transaction_record_id", "")),
        _string_or_blank(row.get("transaction_fingerprint", "")),
        _string_or_blank(lineage.get("db_transaction_id")),
        _string_or_blank(lineage.get("transaction_record_id")),
    }
    return {value for value in aliases if value}


def _resolved_unknown_node(row: pd.Series, side: str) -> tuple[str, str, str, str, str]:
    tx_type = _string_or_blank(row.get("transaction_type", "")).upper()
    cp_name = normalize_text(row.get("counterparty_name", "") or "")
    if (tx_type == "DEPOSIT" and side == "from") or (tx_type == "WITHDRAW" and side == "to"):
        return "CASH:UNSPECIFIED", "Cash", "Cash", "", ""
    if cp_name and cp_name.upper() not in {"UNKNOWN", "NAN", "NONE"}:
        return _node_id_for_entity(cp_name), "Entity", cp_name, "", cp_name
    return "UNKNOWN_COUNTERPARTY", "Unknown", GENERIC_UNKNOWN_LABEL, "", ""


def _resolve_endpoint(row: pd.Series, side: str) -> dict[str, str]:
    endpoint_value = _string_or_blank(row.get("from_account" if side == "from" else "to_account", ""))
    subject_account = _string_or_blank(row.get("subject_account", ""))
    subject_name = normalize_text(row.get("subject_name", "") or "")
    cp_account = _string_or_blank(row.get("counterparty_account", ""))
    cp_partial = _string_or_blank(row.get("partial_account", ""))
    cp_name = normalize_text(row.get("counterparty_name", "") or "")
    bank_name = _string_or_blank(row.get("bank", ""))

    if _is_full_account(endpoint_value):
        account_number = _clean_account(endpoint_value)
        label_name = subject_name if account_number == _clean_account(subject_account) else cp_name
        return {
            "node_id": _node_id_for_account(account_number),
            "node_type": "Account",
            "label": _human_account_label(account_number, label_name),
            "identity_value": account_number,
            "account_number": account_number,
            "partial_account": "",
            "entity_name": label_name,
            "bank_name": bank_name,
        }

    if _is_partial_account(endpoint_value):
        digits = _clean_account(endpoint_value)
        return {
            "node_id": _node_id_for_partial(digits),
            "node_type": "PartialAccount",
            "label": cp_name or f"Partial Account ({digits})",
            "identity_value": digits,
            "account_number": "",
            "partial_account": digits,
            "entity_name": cp_name,
            "bank_name": bank_name,
        }

    if side == "from" and _is_full_account(cp_account):
        account_number = _clean_account(cp_account)
        return {
            "node_id": _node_id_for_account(account_number),
            "node_type": "Account",
            "label": _human_account_label(account_number, cp_name),
            "identity_value": account_number,
            "account_number": account_number,
            "partial_account": "",
            "entity_name": cp_name,
            "bank_name": bank_name,
        }

    if side == "from" and _is_partial_account(cp_partial):
        digits = _clean_account(cp_partial)
        return {
            "node_id": _node_id_for_partial(digits),
            "node_type": "PartialAccount",
            "label": cp_name or f"Partial Account ({digits})",
            "identity_value": digits,
            "account_number": "",
            "partial_account": digits,
            "entity_name": cp_name,
            "bank_name": bank_name,
        }

    node_id, node_type, label, account_number, entity_name = _resolved_unknown_node(row, side)
    return {
        "node_id": node_id,
        "node_type": node_type,
        "label": label,
        "identity_value": account_number or normalize_text(label).lower() or label,
        "account_number": account_number,
        "partial_account": "",
        "entity_name": entity_name,
        "bank_name": bank_name,
    }


def _build_relationship_edge(
    *,
    edge_id: str,
    edge_type: str,
    from_node_id: str,
    to_node_id: str,
    label: str,
    confidence_score: float,
    review_status: str,
    assertion_status: str,
    statement_batch_id: str,
    parser_run_id: str,
    file_id: str,
    source_transaction_ids: str,
    source_row_number: str,
    source_sheet: str,
    source_file: str,
    description: str,
    lineage_payload: dict[str, Any],
    duplicate_status: str = "",
) -> dict[str, Any]:
    return {
        "edge_id": edge_id,
        "edge_type": edge_type,
        "from_node_id": from_node_id,
        "to_node_id": to_node_id,
        "label": label,
        "aggregation_level": "relationship",
        "directionality": "directed",
        "amount": "",
        "amount_display": "",
        "currency": "",
        "date": "",
        "time": "",
        "transaction_count": 0,
        "confidence_score": confidence_score,
        "review_status": review_status,
        "assertion_status": assertion_status,
        "duplicate_status": duplicate_status,
        "transaction_id": "",
        "source_transaction_ids": source_transaction_ids,
        "statement_batch_id": statement_batch_id,
        "parser_run_id": parser_run_id,
        "file_id": file_id,
        "source_row_number": source_row_number,
        "source_sheet": source_sheet,
        "source_file": source_file,
        "reference_no": "",
        "description": description,
        "lineage_json": _json_text(lineage_payload),
    }


def _ownership_edges_from_row(row: pd.Series, lineage: dict[str, Any], transaction_key: str) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    review_status = _string_or_blank(row.get("review_status", ""))
    statement_batch_id = _string_or_blank(row.get("statement_batch_id", "") or lineage.get("statement_batch_id"))
    parser_run_id = _string_or_blank(row.get("parser_run_id", "") or lineage.get("parser_run_id"))
    file_id = _string_or_blank(row.get("file_id", "") or lineage.get("file_id"))
    source_row_number = _string_or_blank(row.get("row_number", "") or lineage.get("source_row_number"))
    source_sheet = _string_or_blank(row.get("source_sheet", "") or lineage.get("sheet"))
    source_file = _string_or_blank(row.get("source_file", "") or lineage.get("source_file"))

    subject_name = normalize_text(row.get("subject_name", "") or lineage.get("subject_name"))
    subject_account = _string_or_blank(row.get("subject_account", "") or lineage.get("subject_account"))
    if subject_name and _is_full_account(subject_account):
        entity_node_payload = {
            "node_id": _node_id_for_entity(subject_name),
            "node_type": "Entity",
            "label": subject_name,
            "identity_value": normalize_text(subject_name).lower(),
            "entity_name": subject_name,
            "bank_name": _string_or_blank(row.get("bank", "")),
        }
        edges.append(
            {
                **_build_relationship_edge(
                    edge_id=_hash_id("OWNS", entity_node_payload["node_id"], _node_id_for_account(subject_account)),
                    edge_type="OWNS",
                    from_node_id=entity_node_payload["node_id"],
                    to_node_id=_node_id_for_account(subject_account),
                    label="Owns",
                    confidence_score=1.0,
                    review_status=review_status,
                    assertion_status="derived_from_statement",
                    statement_batch_id=statement_batch_id,
                    parser_run_id=parser_run_id,
                    file_id=file_id,
                    source_transaction_ids=transaction_key,
                    source_row_number=source_row_number,
                    source_sheet=source_sheet,
                    source_file=source_file,
                    description=f"{subject_name} owns {subject_account}",
                    lineage_payload=lineage,
                ),
                "owner_node_payload": entity_node_payload,
            }
        )

    cp_name = normalize_text(row.get("counterparty_name", "") or "")
    cp_account = _string_or_blank(row.get("counterparty_account", ""))
    partial = _string_or_blank(row.get("partial_account", ""))
    if cp_name and cp_name.upper() not in {"UNKNOWN", "CASH", "ATM CASH", "CASH DEPOSIT"}:
        if _is_full_account(cp_account):
            account_node_id = _node_id_for_account(cp_account)
        elif _is_partial_account(partial):
            account_node_id = _node_id_for_partial(partial)
        else:
            account_node_id = ""
        if account_node_id:
            entity_node_payload = {
                "node_id": _node_id_for_entity(cp_name),
                "node_type": "Entity",
                "label": cp_name,
                "identity_value": normalize_text(cp_name).lower(),
                "entity_name": cp_name,
                "bank_name": _string_or_blank(row.get("bank", "")),
            }
            edges.append(
                {
                    **_build_relationship_edge(
                        edge_id=_hash_id("OWNS", entity_node_payload["node_id"], account_node_id),
                        edge_type="OWNS",
                        from_node_id=entity_node_payload["node_id"],
                        to_node_id=account_node_id,
                        label="Owns",
                        confidence_score=_float_or_zero(row.get("confidence") or row.get("parse_confidence") or 0.65) or 0.65,
                        review_status=review_status,
                        assertion_status="derived_from_statement",
                        statement_batch_id=statement_batch_id,
                        parser_run_id=parser_run_id,
                        file_id=file_id,
                        source_transaction_ids=transaction_key,
                        source_row_number=source_row_number,
                        source_sheet=source_sheet,
                        source_file=source_file,
                        description=f"{cp_name} associated with {cp_account or partial}",
                        lineage_payload=lineage,
                    ),
                    "owner_node_payload": entity_node_payload,
                }
            )

    return edges


def _merge_edge_rows(edge_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}

    for edge in edge_rows:
        edge_id = _string_or_blank(edge.get("edge_id", ""))
        if not edge_id:
            continue
        if edge_id not in merged:
            payload = dict(edge)
            payload["_source_transaction_ids"] = _split_pipe(payload.get("source_transaction_ids"))
            payload["_statement_batch_ids"] = _split_pipe(payload.get("statement_batch_id"))
            payload["_parser_run_ids"] = _split_pipe(payload.get("parser_run_id"))
            payload["_file_ids"] = _split_pipe(payload.get("file_id"))
            payload["_source_row_numbers"] = _split_pipe(payload.get("source_row_number"))
            payload["_source_sheets"] = _split_pipe(payload.get("source_sheet"))
            payload["_source_files"] = _split_pipe(payload.get("source_file"))
            payload["_review_statuses"] = _split_pipe(payload.get("review_status"))
            payload["_lineage_items"] = []
            lineage_payload = _json_dict(payload.get("lineage_json"))
            if lineage_payload:
                payload["_lineage_items"].append(lineage_payload)
            merged[edge_id] = payload
            continue

        current = merged[edge_id]
        current["_source_transaction_ids"].update(_split_pipe(edge.get("source_transaction_ids")))
        current["_statement_batch_ids"].update(_split_pipe(edge.get("statement_batch_id")))
        current["_parser_run_ids"].update(_split_pipe(edge.get("parser_run_id")))
        current["_file_ids"].update(_split_pipe(edge.get("file_id")))
        current["_source_row_numbers"].update(_split_pipe(edge.get("source_row_number")))
        current["_source_sheets"].update(_split_pipe(edge.get("source_sheet")))
        current["_source_files"].update(_split_pipe(edge.get("source_file")))
        current["_review_statuses"].update(_split_pipe(edge.get("review_status")))
        lineage_payload = _json_dict(edge.get("lineage_json"))
        if lineage_payload:
            current["_lineage_items"].append(lineage_payload)
        current["confidence_score"] = max(
            _float_or_zero(current.get("confidence_score")),
            _float_or_zero(edge.get("confidence_score")),
        )
        if not current.get("description") and edge.get("description"):
            current["description"] = edge.get("description")
        if not current.get("label") and edge.get("label"):
            current["label"] = edge.get("label")

    finalized: list[dict[str, Any]] = []
    for edge in merged.values():
        edge["source_transaction_ids"] = _stable_join(edge.pop("_source_transaction_ids", set()))
        edge["statement_batch_id"] = _stable_join(edge.pop("_statement_batch_ids", set()))
        edge["parser_run_id"] = _stable_join(edge.pop("_parser_run_ids", set()))
        edge["file_id"] = _stable_join(edge.pop("_file_ids", set()))
        edge["source_row_number"] = _stable_join(edge.pop("_source_row_numbers", set()))
        edge["source_sheet"] = _stable_join(edge.pop("_source_sheets", set()))
        edge["source_file"] = _stable_join(edge.pop("_source_files", set()))
        edge["review_status"] = _stable_join(edge.pop("_review_statuses", set()))
        lineage_items = edge.pop("_lineage_items", [])
        lineage_payload = {
            "source_transaction_ids": edge["source_transaction_ids"].split("|") if edge["source_transaction_ids"] else [],
            "statement_batch_ids": edge["statement_batch_id"].split("|") if edge["statement_batch_id"] else [],
            "parser_run_ids": edge["parser_run_id"].split("|") if edge["parser_run_id"] else [],
            "file_ids": edge["file_id"].split("|") if edge["file_id"] else [],
            "source_row_numbers": edge["source_row_number"].split("|") if edge["source_row_number"] else [],
            "source_sheets": edge["source_sheet"].split("|") if edge["source_sheet"] else [],
            "source_files": edge["source_file"].split("|") if edge["source_file"] else [],
            "supporting_lineage": lineage_items,
        }
        if edge["source_row_number"]:
            lineage_payload["source_row_number"] = edge["source_row_number"]
        if edge["source_sheet"]:
            lineage_payload["source_sheet"] = edge["source_sheet"]
            lineage_payload["sheet"] = edge["source_sheet"]
        if edge["source_file"]:
            lineage_payload["source_file"] = edge["source_file"]
        edge["lineage_json"] = _json_text(lineage_payload)
        edge["id"] = edge["edge_id"]
        edge["source"] = edge["from_node_id"]
        edge["target"] = edge["to_node_id"]
        edge["type"] = edge["edge_type"]
        finalized.append(edge)

    return sorted(finalized, key=lambda item: (item.get("edge_type", ""), item.get("from_node_id", ""), item.get("to_node_id", ""), item.get("edge_id", "")))


def build_graph_exports(
    transactions: pd.DataFrame,
    *,
    matches: pd.DataFrame | None = None,
    batch_identity: str = "",
    batch_label: str = "",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    tx = transactions.copy().fillna("")
    matches_df = matches.copy().fillna("") if matches is not None else pd.DataFrame()

    node_map: dict[str, dict[str, Any]] = {}
    edge_rows: list[dict[str, Any]] = []
    tx_node_lookup: dict[str, str] = {}

    def upsert_node(
        payload: dict[str, Any],
        *,
        first_seen: str = "",
        last_seen: str = "",
        confidence: float = 0.0,
        lineage: dict[str, Any] | None = None,
    ) -> None:
        node_id = payload["node_id"]
        if node_id not in node_map:
            node_map[node_id] = {
                "id": node_id,
                "node_id": node_id,
                "label": payload.get("label", node_id),
                "type": payload.get("node_type", "Unknown"),
                "node_type": payload.get("node_type", "Unknown"),
                "identity_value": payload.get("identity_value", ""),
                "account_number": payload.get("account_number", ""),
                "partial_account": payload.get("partial_account", ""),
                "entity_name": payload.get("entity_name", ""),
                "bank_name": payload.get("bank_name", ""),
                "transaction_id": payload.get("transaction_id", ""),
                "statement_batch_id": payload.get("statement_batch_id", ""),
                "review_status": "",
                "confidence_score": float(confidence or payload.get("confidence_score", 0.0) or 0.0),
                "source_count": 0,
                "first_seen": "",
                "last_seen": "",
                "_source_transaction_ids": set(),
                "_file_ids": set(),
                "_parser_run_ids": set(),
                "_statement_batch_ids": set(),
                "_source_row_numbers": set(),
                "_source_sheets": set(),
                "_source_files": set(),
                "_review_statuses": set(),
            }
        node = node_map[node_id]
        node["source_count"] += 1
        node["confidence_score"] = max(_float_or_zero(node.get("confidence_score")), _float_or_zero(confidence))
        for key in ("label", "entity_name", "bank_name", "account_number", "partial_account", "identity_value", "transaction_id", "statement_batch_id"):
            if not node.get(key) and payload.get(key):
                node[key] = payload.get(key)
        review_status = _string_or_blank(payload.get("review_status", ""))
        if review_status:
            node["_review_statuses"].add(review_status)
        if first_seen:
            if not node["first_seen"] or first_seen < node["first_seen"]:
                node["first_seen"] = first_seen
        if last_seen:
            if not node["last_seen"] or last_seen > node["last_seen"]:
                node["last_seen"] = last_seen
        if lineage:
            if _string_or_blank(lineage.get("transaction_id")):
                node["_source_transaction_ids"].add(_string_or_blank(lineage.get("transaction_id")))
            if _string_or_blank(lineage.get("file_id")):
                node["_file_ids"].add(_string_or_blank(lineage.get("file_id")))
            if _string_or_blank(lineage.get("parser_run_id")):
                node["_parser_run_ids"].add(_string_or_blank(lineage.get("parser_run_id")))
            if _string_or_blank(lineage.get("statement_batch_id")):
                node["_statement_batch_ids"].add(_string_or_blank(lineage.get("statement_batch_id")))
            if _string_or_blank(lineage.get("source_row_number")):
                node["_source_row_numbers"].add(_string_or_blank(lineage.get("source_row_number")))
            if _string_or_blank(lineage.get("sheet")):
                node["_source_sheets"].add(_string_or_blank(lineage.get("sheet")))
            if _string_or_blank(lineage.get("source_file")):
                node["_source_files"].add(_string_or_blank(lineage.get("source_file")))

    for _, row in tx.iterrows():
        lineage = _extract_lineage(row)
        transaction_key = _stable_transaction_key(row)
        transaction_node_id = _node_id_for_transaction(transaction_key)
        for alias in _transaction_aliases(row, transaction_key):
            tx_node_lookup[alias] = transaction_node_id

        transaction_date = _string_or_blank(row.get("date", ""))[:10]
        confidence = _float_or_zero(row.get("confidence") or row.get("parse_confidence"))
        statement_batch_id = _string_or_blank(row.get("statement_batch_id", "") or lineage.get("statement_batch_id") or batch_identity)
        parser_run_id = _string_or_blank(row.get("parser_run_id", "") or lineage.get("parser_run_id"))
        file_id = _string_or_blank(row.get("file_id", "") or lineage.get("file_id"))
        bank_name = _string_or_blank(row.get("bank", "") or lineage.get("bank") or lineage.get("bank_detected"))
        source_row_number = _string_or_blank(row.get("row_number", "") or lineage.get("source_row_number"))
        source_sheet = _string_or_blank(row.get("source_sheet", "") or lineage.get("sheet"))
        source_file = _string_or_blank(row.get("source_file", "") or lineage.get("source_file"))

        source_node = _resolve_endpoint(row, "from")
        target_node = _resolve_endpoint(row, "to")
        if source_node["node_id"] == "UNKNOWN_COUNTERPARTY" and target_node["node_id"] == "UNKNOWN_COUNTERPARTY":
            continue

        lineage_anchor = {
            "transaction_id": transaction_key,
            "file_id": file_id,
            "parser_run_id": parser_run_id,
            "statement_batch_id": statement_batch_id,
            "source_row_number": source_row_number,
            "sheet": source_sheet,
            "source_file": source_file,
        }
        upsert_node(
            {**source_node, "review_status": _string_or_blank(row.get("review_status", ""))},
            first_seen=transaction_date,
            last_seen=transaction_date,
            confidence=confidence,
            lineage=lineage_anchor,
        )
        upsert_node(
            {**target_node, "review_status": _string_or_blank(row.get("review_status", ""))},
            first_seen=transaction_date,
            last_seen=transaction_date,
            confidence=confidence,
            lineage=lineage_anchor,
        )

        upsert_node(
            {
                "node_id": transaction_node_id,
                "node_type": "Transaction",
                "label": _transaction_label(row, transaction_key),
                "identity_value": transaction_key,
                "transaction_id": transaction_key,
                "statement_batch_id": statement_batch_id,
                "review_status": _string_or_blank(row.get("review_status", "")),
            },
            first_seen=transaction_date,
            last_seen=transaction_date,
            confidence=confidence,
            lineage=lineage_anchor,
        )

        for edge in _ownership_edges_from_row(row, lineage, transaction_key):
            edge_rows.append(edge)
            owner_node_payload = edge.get("owner_node_payload")
            if owner_node_payload:
                upsert_node(
                    owner_node_payload,
                    first_seen=transaction_date,
                    last_seen=transaction_date,
                    confidence=_float_or_zero(edge.get("confidence_score")),
                    lineage=lineage_anchor,
                )

        if bank_name:
            bank_node_id = _node_id_for_bank(bank_name)
            upsert_node(
                {
                    "node_id": bank_node_id,
                    "node_type": "Bank",
                    "label": bank_name,
                    "identity_value": bank_name,
                    "bank_name": bank_name,
                },
                first_seen=transaction_date,
                last_seen=transaction_date,
                confidence=1.0,
                lineage=lineage_anchor,
            )
        else:
            bank_node_id = ""

        batch_node_id = ""
        if statement_batch_id or batch_label:
            batch_node_id = _node_id_for_batch(
                statement_batch_id,
                _string_or_blank(row.get("subject_account", "") or lineage.get("subject_account")),
                bank_name,
                [transaction_date],
            )
            label = batch_label or f"{bank_name or 'Statement'} {format_date_range([transaction_date]) if transaction_date else ''}".strip()
            upsert_node(
                {
                    "node_id": batch_node_id,
                    "node_type": "StatementBatch",
                    "label": label or "Statement Batch",
                    "identity_value": statement_batch_id or label,
                    "statement_batch_id": statement_batch_id,
                    "bank_name": bank_name,
                },
                first_seen=transaction_date,
                last_seen=transaction_date,
                confidence=1.0,
                lineage=lineage_anchor,
            )

        amount = _float_or_zero(row.get("amount"))
        currency = _string_or_blank(row.get("currency", "THB")) or "THB"
        flow_date = _format_date_display(row.get("date", ""))
        flow_time = _string_or_blank(row.get("time", ""))
        flow_lineage = {
            **lineage,
            "source_row_number": source_row_number,
            "sheet": source_sheet,
            "source_file": source_file,
            "from_node_id": source_node["node_id"],
            "to_node_id": target_node["node_id"],
            "direction": _string_or_blank(row.get("direction", "")),
        }
        edge_type = "SENT_TO" if _string_or_blank(row.get("direction", "")).upper() == "OUT" else "RECEIVED_FROM"
        edge_rows.append(
            {
                "edge_id": f"FLOW:{transaction_key}",
                "edge_type": edge_type,
                "from_node_id": source_node["node_id"],
                "to_node_id": target_node["node_id"],
                "label": f"{edge_type.replace('_', ' ').title()} {abs(amount):,.2f} {currency}",
                "aggregation_level": "transaction",
                "directionality": "directed",
                "amount": abs(amount),
                "amount_display": _format_money_display(amount),
                "currency": currency,
                "date": flow_date,
                "time": flow_time,
                "transaction_count": 1,
                "confidence_score": confidence,
                "review_status": _string_or_blank(row.get("review_status", "")),
                "assertion_status": "derived_from_statement",
                "duplicate_status": _string_or_blank(row.get("duplicate_status", "")),
                "transaction_id": transaction_key,
                "source_transaction_ids": transaction_key,
                "statement_batch_id": statement_batch_id,
                "parser_run_id": parser_run_id,
                "file_id": file_id,
                "source_row_number": source_row_number,
                "source_sheet": source_sheet,
                "source_file": source_file,
                "reference_no": _string_or_blank(row.get("reference_no", "")),
                "description": _string_or_blank(row.get("description", "")),
                "lineage_json": _json_text(flow_lineage),
            }
        )

        if batch_node_id:
            edge_rows.append(
                _build_relationship_edge(
                    edge_id=f"APPEARS_IN:{transaction_node_id}:{batch_node_id}",
                    edge_type="APPEARS_IN",
                    from_node_id=transaction_node_id,
                    to_node_id=batch_node_id,
                    label="Appears in",
                    confidence_score=1.0,
                    review_status=_string_or_blank(row.get("review_status", "")),
                    assertion_status="lineage",
                    statement_batch_id=statement_batch_id,
                    parser_run_id=parser_run_id,
                    file_id=file_id,
                    source_transaction_ids=transaction_key,
                    source_row_number=source_row_number,
                    source_sheet=source_sheet,
                    source_file=source_file,
                    description="Transaction appears in statement batch",
                    lineage_payload=flow_lineage,
                    duplicate_status=_string_or_blank(row.get("duplicate_status", "")),
                )
            )
            edge_rows.append(
                _build_relationship_edge(
                    edge_id=f"APPEARS_IN:{source_node['node_id']}:{batch_node_id}",
                    edge_type="APPEARS_IN",
                    from_node_id=source_node["node_id"],
                    to_node_id=batch_node_id,
                    label="Appears in",
                    confidence_score=1.0,
                    review_status=_string_or_blank(row.get("review_status", "")),
                    assertion_status="lineage",
                    statement_batch_id=statement_batch_id,
                    parser_run_id=parser_run_id,
                    file_id=file_id,
                    source_transaction_ids=transaction_key,
                    source_row_number=source_row_number,
                    source_sheet=source_sheet,
                    source_file=source_file,
                    description="Node appears in statement batch",
                    lineage_payload=flow_lineage,
                    duplicate_status=_string_or_blank(row.get("duplicate_status", "")),
                )
            )
            edge_rows.append(
                _build_relationship_edge(
                    edge_id=f"APPEARS_IN:{target_node['node_id']}:{batch_node_id}",
                    edge_type="APPEARS_IN",
                    from_node_id=target_node["node_id"],
                    to_node_id=batch_node_id,
                    label="Appears in",
                    confidence_score=1.0,
                    review_status=_string_or_blank(row.get("review_status", "")),
                    assertion_status="lineage",
                    statement_batch_id=statement_batch_id,
                    parser_run_id=parser_run_id,
                    file_id=file_id,
                    source_transaction_ids=transaction_key,
                    source_row_number=source_row_number,
                    source_sheet=source_sheet,
                    source_file=source_file,
                    description="Node appears in statement batch",
                    lineage_payload=flow_lineage,
                    duplicate_status=_string_or_blank(row.get("duplicate_status", "")),
                )
            )
        if bank_node_id and batch_node_id:
            edge_rows.append(
                _build_relationship_edge(
                    edge_id=f"APPEARS_IN:{batch_node_id}:{bank_node_id}",
                    edge_type="APPEARS_IN",
                    from_node_id=batch_node_id,
                    to_node_id=bank_node_id,
                    label="Issued by bank",
                    confidence_score=1.0,
                    review_status="",
                    assertion_status="lineage",
                    statement_batch_id=statement_batch_id,
                    parser_run_id=parser_run_id,
                    file_id=file_id,
                    source_transaction_ids=transaction_key,
                    source_row_number=source_row_number,
                    source_sheet=source_sheet,
                    source_file=source_file,
                    description="Statement batch issued by bank",
                    lineage_payload=flow_lineage,
                )
            )

    if not matches_df.empty:
        for _, match in matches_df.iterrows():
            status = _string_or_blank(match.get("status", "")).lower()
            if status == "rejected":
                continue
            source_tx = _string_or_blank(match.get("source_transaction_id", ""))
            target_tx = _string_or_blank(match.get("target_transaction_id", ""))
            target_account = _string_or_blank(match.get("target_account_number", "") or match.get("target_account_id", ""))
            if not source_tx:
                continue

            source_tx_node = tx_node_lookup.get(source_tx, _node_id_for_transaction(source_tx))
            upsert_node(
                {
                    "node_id": source_tx_node,
                    "node_type": "Transaction",
                    "label": source_tx,
                    "identity_value": source_tx,
                    "transaction_id": source_tx,
                    "review_status": status or "suggested",
                },
                confidence=_float_or_zero(match.get("confidence_score")),
            )

            if target_tx:
                target_node_id = tx_node_lookup.get(target_tx, _node_id_for_transaction(target_tx))
                upsert_node(
                    {
                        "node_id": target_node_id,
                        "node_type": "Transaction",
                        "label": target_tx,
                        "identity_value": target_tx,
                        "transaction_id": target_tx,
                        "review_status": status or "suggested",
                    },
                    confidence=_float_or_zero(match.get("confidence_score")),
                )
            elif _is_full_account(target_account):
                target_node_id = _node_id_for_account(target_account)
                upsert_node(
                    {
                        "node_id": target_node_id,
                        "node_type": "Account",
                        "label": target_account,
                        "identity_value": target_account,
                        "account_number": target_account,
                        "review_status": status or "suggested",
                    },
                    confidence=_float_or_zero(match.get("confidence_score")),
                )
            else:
                continue

            edge_type = "MATCHED_TO" if status == "confirmed" else "POSSIBLE_SAME_AS"
            is_manual_confirmed = bool(match.get("is_manual_confirmed"))
            if status == "confirmed" and is_manual_confirmed:
                assertion_status = "manual_confirmed"
            elif status == "confirmed":
                assertion_status = "confirmed"
            else:
                assertion_status = "system_suggested"
            evidence = match.get("evidence_json", "")
            edge_rows.append(
                {
                    "edge_id": _string_or_blank(match.get("edge_id", "")) or _hash_id("MATCH", source_tx_node, target_node_id, match.get("match_type", ""), status or "suggested"),
                    "edge_type": edge_type,
                    "from_node_id": source_tx_node,
                    "to_node_id": target_node_id,
                    "label": _string_or_blank(match.get("match_type", edge_type)),
                    "aggregation_level": "relationship",
                    "directionality": "directed",
                    "amount": "",
                    "currency": "",
                    "transaction_count": 0,
                    "confidence_score": _float_or_zero(match.get("confidence_score")),
                    "review_status": status or "suggested",
                    "assertion_status": assertion_status,
                    "duplicate_status": "",
                    "transaction_id": source_tx,
                    "source_transaction_ids": _stable_join([source_tx, target_tx]),
                    "statement_batch_id": "",
                    "parser_run_id": "",
                    "file_id": "",
                    "source_row_number": "",
                    "source_sheet": "",
                    "source_file": "",
                    "reference_no": "",
                    "description": _string_or_blank(match.get("match_type", edge_type)),
                    "lineage_json": _json_text(evidence),
                }
            )

    finalized_nodes: list[dict[str, Any]] = []
    for node_id, node in sorted(node_map.items()):
        source_transaction_ids = sorted(node.pop("_source_transaction_ids", set()))
        file_ids = sorted(node.pop("_file_ids", set()))
        parser_run_ids = sorted(node.pop("_parser_run_ids", set()))
        statement_batch_ids = sorted(node.pop("_statement_batch_ids", set()))
        source_row_numbers = sorted(node.pop("_source_row_numbers", set()))
        source_sheets = sorted(node.pop("_source_sheets", set()))
        source_files = sorted(node.pop("_source_files", set()))
        review_statuses = sorted(node.pop("_review_statuses", set()))

        node["review_status"] = "|".join(review_statuses)
        node["source_transaction_ids"] = "|".join(source_transaction_ids)
        node["file_ids"] = "|".join(file_ids)
        node["parser_run_ids"] = "|".join(parser_run_ids)
        node["statement_batch_ids"] = "|".join(statement_batch_ids)
        node["source_row_numbers"] = "|".join(source_row_numbers)
        node["source_sheets"] = "|".join(source_sheets)
        node["source_files"] = "|".join(source_files)
        node["lineage_json"] = _json_text(
            {
                "source_transaction_ids": source_transaction_ids,
                "file_ids": file_ids,
                "parser_run_ids": parser_run_ids,
                "statement_batch_ids": statement_batch_ids,
                "source_row_numbers": source_row_numbers,
                "source_sheets": source_sheets,
                "source_files": source_files,
            }
        )
        finalized_nodes.append(node)
    nodes_df = pd.DataFrame(finalized_nodes, columns=GRAPH_NODE_COLUMNS).fillna("")

    merged_edges = _merge_edge_rows(edge_rows)
    edges_df = pd.DataFrame(merged_edges, columns=GRAPH_EDGE_COLUMNS).fillna("")

    flow_edges = edges_df[edges_df["aggregation_level"] == "transaction"].copy()
    aggregate_rows: list[dict[str, Any]] = []
    if not flow_edges.empty:
        grouped = flow_edges.groupby(["from_node_id", "to_node_id", "edge_type", "currency"], dropna=False)
        for (from_node_id, to_node_id, edge_type, currency), group in grouped:
            transaction_ids = sorted({value for cell in group["source_transaction_ids"].astype(str).tolist() for value in _split_pipe(cell)})
            if not transaction_ids:
                transaction_ids = sorted({value for value in group["transaction_id"].astype(str).tolist() if value})
            row_numbers = sorted({value for cell in group["source_row_number"].astype(str).tolist() for value in _split_pipe(cell)})
            sheets = sorted({value for cell in group["source_sheet"].astype(str).tolist() for value in _split_pipe(cell)})
            source_files = sorted({value for cell in group["source_file"].astype(str).tolist() for value in _split_pipe(cell)})
            dates = sorted({value for value in group["date"].astype(str).tolist() if value})
            review_statuses = sorted({value for cell in group["review_status"].astype(str).tolist() for value in _split_pipe(cell)})
            parser_run_ids = sorted({value for cell in group["parser_run_id"].astype(str).tolist() for value in _split_pipe(cell)})
            file_ids = sorted({value for cell in group["file_id"].astype(str).tolist() for value in _split_pipe(cell)})
            batch_ids = sorted({value for cell in group["statement_batch_id"].astype(str).tolist() for value in _split_pipe(cell)})
            confidences = pd.to_numeric(group["confidence_score"], errors="coerce").fillna(0.0)
            amounts = pd.to_numeric(group["amount"], errors="coerce").fillna(0.0)
            signed_multiplier = -1.0 if edge_type == "SENT_TO" else 1.0
            aggregate_rows.append(
                {
                    "id": _hash_id("FLOW_AGG", from_node_id, to_node_id, edge_type, currency),
                    "edge_id": _hash_id("FLOW_AGG", from_node_id, to_node_id, edge_type, currency),
                    "source": from_node_id,
                    "from_node_id": from_node_id,
                    "target": to_node_id,
                    "to_node_id": to_node_id,
                    "label": f"{edge_type.replace('_', ' ').title()} ({len(transaction_ids) or len(group)} transactions)",
                    "type": edge_type,
                    "edge_type": edge_type,
                    "aggregation_level": "aggregate",
                    "directionality": "directed",
                    "transaction_count": len(transaction_ids) or len(group),
                    "total_amount_signed": round(float(amounts.sum() * signed_multiplier), 2),
                    "total_amount_abs": round(float(amounts.abs().sum()), 2),
                    "total_amount_display": _format_money_display(amounts.abs().sum()),
                    "currency": currency,
                    "date_range": " | ".join(dates),
                    "confidence_score_avg": round(float(confidences.mean()), 4) if len(confidences) else 0.0,
                    "confidence_score_min": round(float(confidences.min()), 4) if len(confidences) else 0.0,
                    "confidence_score_max": round(float(confidences.max()), 4) if len(confidences) else 0.0,
                    "review_status": "|".join(review_statuses),
                    "assertion_status": "derived_from_statement",
                    "source_transaction_ids": "|".join(transaction_ids),
                    "statement_batch_id": "|".join(batch_ids),
                    "parser_run_id": "|".join(parser_run_ids),
                    "file_id": "|".join(file_ids),
                    "source_row_numbers": "|".join(row_numbers),
                    "source_sheets": "|".join(sheets),
                    "source_files": "|".join(source_files),
                    "lineage_json": _json_text(
                        {
                            "source_edge_ids": sorted(group["edge_id"].astype(str).tolist()),
                            "source_transaction_ids": transaction_ids,
                            "source_row_numbers": row_numbers,
                            "source_sheets": sheets,
                            "source_files": source_files,
                        }
                    ),
                }
            )
    aggregated_df = pd.DataFrame(aggregate_rows, columns=AGGREGATED_EDGE_COLUMNS).fillna("")

    manifest = {
        "schema_version": "1.3",
        "node_columns": GRAPH_NODE_COLUMNS,
        "edge_columns": GRAPH_EDGE_COLUMNS,
        "aggregated_edge_columns": AGGREGATED_EDGE_COLUMNS,
        "derived_account_edge_columns": DERIVED_ACCOUNT_EDGE_COLUMNS,
        "supported_node_types": SUPPORTED_NODE_TYPES,
        "supported_edge_types": SUPPORTED_EDGE_TYPES,
        "node_count": len(nodes_df),
        "edge_count": len(edges_df),
        "aggregated_edge_count": len(aggregated_df),
        "contains_match_edges": bool((edges_df["edge_type"].isin(["MATCHED_TO", "POSSIBLE_SAME_AS"])).any()) if not edges_df.empty else False,
        "contains_only_confirmed_match_edges_in_confirmed_class": True,
    }

    return nodes_df, edges_df, aggregated_df, manifest


def build_derived_account_edges(aggregated_df: pd.DataFrame) -> pd.DataFrame:
    """
    Derive explicit account-to-account flow edges from aggregated transaction-flow
    edges. This keeps the source graph intact while also producing a compact,
    analyst-friendly relationship layer for downstream graph tooling.
    """
    if aggregated_df.empty:
        return pd.DataFrame(columns=DERIVED_ACCOUNT_EDGE_COLUMNS)

    derived_rows: list[dict[str, Any]] = []
    for _, row in aggregated_df.fillna("").iterrows():
        from_node_id = _string_or_blank(row.get("from_node_id", ""))
        to_node_id = _string_or_blank(row.get("to_node_id", ""))
        if not (from_node_id.startswith("ACCOUNT:") and to_node_id.startswith("ACCOUNT:")):
            continue

        source_transaction_ids = _string_or_blank(row.get("source_transaction_ids", ""))
        tx_count = int(_float_or_zero(row.get("transaction_count")))
        label = f"Account to Account Flow ({tx_count} transactions)" if tx_count else "Account to Account Flow"
        derived_rows.append(
            {
                "id": _hash_id("DERIVED_FLOW", from_node_id, to_node_id, row.get("currency", ""), row.get("source_transaction_ids", "")),
                "edge_id": _hash_id("DERIVED_FLOW", from_node_id, to_node_id, row.get("currency", ""), row.get("source_transaction_ids", "")),
                "source": from_node_id,
                "from_node_id": from_node_id,
                "target": to_node_id,
                "to_node_id": to_node_id,
                "label": label,
                "type": "DERIVED_ACCOUNT_TO_ACCOUNT",
                "edge_type": "DERIVED_ACCOUNT_TO_ACCOUNT",
                "aggregation_level": "derived_account",
                "directionality": "directed",
                "transaction_count": tx_count,
                "total_amount_signed": round(_float_or_zero(row.get("total_amount_signed")), 2),
                "total_amount_abs": round(_float_or_zero(row.get("total_amount_abs")), 2),
                "total_amount_display": _string_or_blank(row.get("total_amount_display", "")),
                "currency": _string_or_blank(row.get("currency", "")),
                "date_range": _string_or_blank(row.get("date_range", "")),
                "confidence_score_avg": round(_float_or_zero(row.get("confidence_score_avg")), 4),
                "confidence_score_min": round(_float_or_zero(row.get("confidence_score_min")), 4),
                "confidence_score_max": round(_float_or_zero(row.get("confidence_score_max")), 4),
                "review_status": _string_or_blank(row.get("review_status", "")),
                "assertion_status": "derived_from_statement_flow",
                "source_transaction_ids": source_transaction_ids,
                "statement_batch_id": _string_or_blank(row.get("statement_batch_id", "")),
                "parser_run_id": _string_or_blank(row.get("parser_run_id", "")),
                "file_id": _string_or_blank(row.get("file_id", "")),
                "source_row_numbers": _string_or_blank(row.get("source_row_numbers", "")),
                "source_sheets": _string_or_blank(row.get("source_sheets", "")),
                "source_files": _string_or_blank(row.get("source_files", "")),
                "lineage_json": _json_text(
                    {
                        "derived_from_edge_id": _string_or_blank(row.get("edge_id", "")),
                        "source_transaction_ids": source_transaction_ids.split("|") if source_transaction_ids else [],
                        "statement_batch_ids": sorted(_split_pipe(row.get("statement_batch_id", ""))),
                        "parser_run_ids": sorted(_split_pipe(row.get("parser_run_id", ""))),
                        "file_ids": sorted(_split_pipe(row.get("file_id", ""))),
                        "source_row_numbers": sorted(_split_pipe(row.get("source_row_numbers", ""))),
                        "source_sheets": sorted(_split_pipe(row.get("source_sheets", ""))),
                        "source_files": sorted(_split_pipe(row.get("source_files", ""))),
                        "directionality": "directed",
                    }
                ),
            }
        )

    return pd.DataFrame(derived_rows, columns=DERIVED_ACCOUNT_EDGE_COLUMNS).fillna("")


def build_graph_bundle(
    transactions: pd.DataFrame,
    *,
    matches: pd.DataFrame | None = None,
    batch_identity: str = "",
    batch_label: str = "",
) -> dict[str, Any]:
    """
    Build the full Phase 1 graph foundation bundle from finalized BSIE normalized
    transactions.
    """
    nodes_df, edges_df, aggregated_df, manifest = build_graph_exports(
        transactions,
        matches=matches,
        batch_identity=batch_identity,
        batch_label=batch_label,
    )
    derived_account_edges_df = build_derived_account_edges(aggregated_df)
    manifest = {
        **manifest,
        "derived_account_edge_count": len(derived_account_edges_df),
    }
    return {
        "nodes_df": nodes_df,
        "edges_df": edges_df,
        "aggregated_df": aggregated_df,
        "derived_account_edges_df": derived_account_edges_df,
        "manifest": manifest,
    }


def write_graph_exports(
    output_dir: Path,
    *,
    transactions: pd.DataFrame,
    matches: pd.DataFrame | None = None,
    batch_identity: str = "",
    batch_label: str = "",
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    graph_bundle = build_graph_bundle(
        transactions,
        matches=matches,
        batch_identity=batch_identity,
        batch_label=batch_label,
    )
    nodes_df = graph_bundle["nodes_df"]
    edges_df = graph_bundle["edges_df"]
    aggregated_df = graph_bundle["aggregated_df"]
    derived_account_edges_df = graph_bundle["derived_account_edges_df"]
    manifest = graph_bundle["manifest"]
    nodes_path = output_dir / "nodes.csv"
    edges_path = output_dir / "edges.csv"
    aggregated_path = output_dir / "aggregated_edges.csv"
    derived_account_edges_path = output_dir / "derived_account_edges.csv"
    nodes_json_path = output_dir / GRAPH_EXPORT_JSON_FILENAMES["nodes"]
    edges_json_path = output_dir / GRAPH_EXPORT_JSON_FILENAMES["edges"]
    aggregated_json_path = output_dir / GRAPH_EXPORT_JSON_FILENAMES["aggregated_edges"]
    derived_account_edges_json_path = output_dir / GRAPH_EXPORT_JSON_FILENAMES["derived_account_edges"]
    manifest_path = output_dir / "graph_manifest.json"

    nodes_df.to_csv(nodes_path, index=False, encoding="utf-8-sig")
    edges_df.to_csv(edges_path, index=False, encoding="utf-8-sig")
    aggregated_df.to_csv(aggregated_path, index=False, encoding="utf-8-sig")
    derived_account_edges_df.to_csv(derived_account_edges_path, index=False, encoding="utf-8-sig")
    nodes_json_path.write_text(nodes_df.to_json(orient="records", force_ascii=False, indent=2), encoding="utf-8")
    edges_json_path.write_text(edges_df.to_json(orient="records", force_ascii=False, indent=2), encoding="utf-8")
    aggregated_json_path.write_text(aggregated_df.to_json(orient="records", force_ascii=False, indent=2), encoding="utf-8")
    derived_account_edges_json_path.write_text(
        derived_account_edges_df.to_json(orient="records", force_ascii=False, indent=2),
        encoding="utf-8",
    )
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "nodes_path": nodes_path,
        "edges_path": edges_path,
        "aggregated_edges_path": aggregated_path,
        "derived_account_edges_path": derived_account_edges_path,
        "nodes_json_path": nodes_json_path,
        "edges_json_path": edges_json_path,
        "aggregated_edges_json_path": aggregated_json_path,
        "derived_account_edges_json_path": derived_account_edges_json_path,
        "manifest_path": manifest_path,
        "manifest": manifest,
        "nodes_df": nodes_df,
        "edges_df": edges_df,
        "aggregated_df": aggregated_df,
        "derived_account_edges_df": derived_account_edges_df,
    }
