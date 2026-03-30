"""
ofx_io.py
---------
Minimal OFX bank-account import/export helpers for BSIE.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd


_TAG_RE = re.compile(r"<(?P<tag>[A-Z0-9]+)>(?P<value>.*)")


def _parse_ofx_datetime(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"\[.*?\]$", "", text)
    digits = re.sub(r"[^0-9]", "", text)
    if len(digits) >= 14:
        return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]} {digits[8:10]}:{digits[10:12]}:{digits[12:14]}"
    if len(digits) >= 8:
        return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"
    return text


def _parse_block(lines: list[str], block_name: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    in_block = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.upper() == f"<{block_name}>":
            current = {}
            in_block = True
            continue
        if line.upper() == f"</{block_name}>":
            if current is not None:
                records.append(current)
            current = None
            in_block = False
            continue
        if not in_block or current is None:
            continue
        match = _TAG_RE.match(line)
        if match:
            current[match.group("tag")] = match.group("value").strip()

    return records


def _parse_singletons(lines: list[str], tags: set[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in lines:
        match = _TAG_RE.match(raw_line.strip())
        if not match:
            continue
        tag = match.group("tag")
        if tag in tags and tag not in values:
            values[tag] = match.group("value").strip()
    return values


def parse_ofx_file(file_path: str | Path) -> pd.DataFrame:
    path = Path(file_path)
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    account_meta = _parse_singletons(lines, {"ACCTID", "BANKID", "ACCTTYPE", "LEDGERBAL", "BALAMT"})
    transactions = _parse_block(lines, "STMTTRN")

    rows: list[dict[str, Any]] = []
    for index, txn in enumerate(transactions, start=1):
        posted = _parse_ofx_datetime(txn.get("DTPOSTED", ""))
        amount = float(txn.get("TRNAMT", "0") or 0)
        date_part, _, time_part = posted.partition(" ")
        rows.append(
            {
                "date": date_part,
                "time": time_part,
                "description": txn.get("MEMO") or txn.get("NAME") or txn.get("FITID") or "",
                "amount": amount,
                "balance": account_meta.get("BALAMT", ""),
                "subject_account": account_meta.get("ACCTID", ""),
                "subject_name": "",
                "bank": "OFX",
                "counterparty_account": "",
                "counterparty_name": txn.get("NAME", "") or txn.get("MEMO", ""),
                "partial_account": "",
                "channel": txn.get("TRNTYPE", ""),
                "direction": "IN" if amount > 0 else "OUT" if amount < 0 else "UNKNOWN",
                "transaction_type": "",
                "confidence": 1.0,
                "from_account": "",
                "to_account": "",
                "raw_account_value": "",
                "parsed_account_type": "",
                "balance_source": "STATEMENT" if account_meta.get("BALAMT") else "",
                "source_format": "OFX",
                "fit_id": txn.get("FITID", ""),
                "trn_type": txn.get("TRNTYPE", ""),
                "row_number": index,
            }
        )

    return pd.DataFrame(rows)


def infer_identity_from_ofx(file_path: str | Path, tx_df: pd.DataFrame | None = None) -> dict[str, str]:
    tx_df = tx_df if tx_df is not None else parse_ofx_file(file_path)
    account = ""
    if not tx_df.empty and "subject_account" in tx_df.columns:
        account = str(tx_df.iloc[0].get("subject_account", "") or "").strip()
    name = Path(file_path).stem
    return {"account": account, "name": name}


def export_ofx(transactions: pd.DataFrame, account_number: str, bank: str, subject_name: str = "") -> str:
    now = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    start_date = ""
    end_date = ""
    if not transactions.empty and "date" in transactions.columns:
        dates = [str(value) for value in transactions["date"].fillna("").tolist() if str(value)]
        if dates:
            start_date = min(dates).replace("-", "")
            end_date = max(dates).replace("-", "")
    closing_balance = 0.0
    if not transactions.empty and "balance" in transactions.columns:
        balances = [value for value in transactions["balance"].tolist() if str(value).strip() not in {"", "nan", "None"}]
        if balances:
            closing_balance = float(balances[-1])

    lines = [
        "OFXHEADER:100",
        "DATA:OFXSGML",
        "VERSION:102",
        "SECURITY:NONE",
        "ENCODING:UTF-8",
        "CHARSET:UTF-8",
        "COMPRESSION:NONE",
        "OLDFILEUID:NONE",
        f"NEWFILEUID:{now}",
        "",
        "<OFX>",
        "  <SIGNONMSGSRSV1>",
        "    <SONRS>",
        "      <STATUS>",
        "        <CODE>0",
        "        <SEVERITY>INFO",
        "      </STATUS>",
        f"      <DTSERVER>{now}",
        "      <LANGUAGE>ENG",
        "    </SONRS>",
        "  </SIGNONMSGSRSV1>",
        "  <BANKMSGSRSV1>",
        "    <STMTTRNRS>",
        "      <TRNUID>1",
        "      <STATUS>",
        "        <CODE>0",
        "        <SEVERITY>INFO",
        "      </STATUS>",
        "      <STMTRS>",
        f"        <CURDEF>{'THB'}",
        "        <BANKACCTFROM>",
        f"          <BANKID>{bank}",
        f"          <ACCTID>{account_number}",
        "          <ACCTTYPE>CHECKING",
        "        </BANKACCTFROM>",
        "        <BANKTRANLIST>",
        f"          <DTSTART>{start_date or now[:8]}",
        f"          <DTEND>{end_date or now[:8]}",
    ]

    for _, row in transactions.fillna("").iterrows():
        date = str(row.get("date", "") or "").replace("-", "")
        time = str(row.get("time", "") or "").replace(":", "")
        posted = f"{date}{time or '000000'}"
        lines.extend(
            [
                "          <STMTTRN>",
                f"            <TRNTYPE>{'CREDIT' if float(row.get('amount') or 0) > 0 else 'DEBIT'}",
                f"            <DTPOSTED>{posted or now}",
                f"            <TRNAMT>{float(row.get('amount') or 0):.2f}",
                f"            <FITID>{row.get('transaction_id') or row.get('fit_id') or posted}",
                f"            <NAME>{str(row.get('counterparty_name') or row.get('description') or subject_name)[:64]}",
                f"            <MEMO>{str(row.get('description') or '')[:255]}",
                "          </STMTTRN>",
            ]
        )

    lines.extend(
        [
            "        </BANKTRANLIST>",
            "        <LEDGERBAL>",
            f"          <BALAMT>{closing_balance:.2f}",
            f"          <DTASOF>{now}",
            "        </LEDGERBAL>",
            "      </STMTRS>",
            "    </STMTTRNRS>",
            "  </BANKMSGSRSV1>",
            "</OFX>",
        ]
    )
    return "\n".join(lines) + "\n"
