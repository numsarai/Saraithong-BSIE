"""
exporter.py
-----------
Exports the Account Package to disk in CSV and multi-sheet Excel (.xlsx).

Output structure:
  /data/output/{account_number}/
      raw/original.xlsx
      processed/
          {name}_{bank}_report.xlsx    ← multi-sheet report
          transactions.csv
          entities.csv   entities.xlsx
          links.csv
      meta.json
"""

import json
import logging
import re
import shutil
from pathlib import Path
from typing import Optional, Union, Tuple

import pandas as pd

from utils.date_utils import format_date_range
from core.export_anx import export_anx

logger = logging.getLogger(__name__)

from paths import OUTPUT_DIR as BASE_OUTPUT


TRANSACTION_EXPORT_COLUMNS = [
    "transaction_id",
    "date",
    "time",
    "transaction_type",
    "direction",
    "amount",
    "currency",
    "balance",
    "subject_account",
    "subject_name",
    "counterparty_account",
    "partial_account",
    "counterparty_name",
    "from_account",
    "to_account",
    "bank",
    "channel",
    "description",
    "confidence",
    "is_overridden",
    "override_from_account",
    "override_to_account",
    "override_reason",
    "override_by",
    "override_timestamp",
    "raw_account_value",
    "parsed_account_type",
    "nlp_type_hint",
    "nlp_confidence",
    "nlp_best_name",
    "source_file",
    "row_number",
]

ENTITY_EXPORT_COLUMNS = [
    "entity_id",
    "entity_type",
    "entity_label",
    "identity_value",
    "account_number",
    "name",
    "first_seen",
    "last_seen",
    "transaction_count",
    "source_transaction_ids",
]

LINK_EXPORT_COLUMNS = [
    "link_id",
    "transaction_id",
    "date",
    "transaction_type",
    "direction",
    "amount",
    "currency",
    "from_account",
    "from_entity_id",
    "from_label",
    "to_account",
    "to_entity_id",
    "to_label",
    "counterparty_name",
    "description",
]

TRANSACTION_CATEGORY_RULES = {
    "transfer_in": {"transaction_type": "IN_TRANSFER"},
    "transfer_out": {"transaction_type": "OUT_TRANSFER"},
    "deposit": {"transaction_type": "DEPOSIT"},
    "withdraw": {"transaction_type": "WITHDRAW"},
}


def _safe_filename(name: str) -> str:
    """Sanitise a string for use in a file name (keep Thai, alphanumeric, space, dash)."""
    s = re.sub(r'[\\/:*?"<>|]', '', name).strip()
    # collapse multiple spaces / dots
    s = re.sub(r'\s+', ' ', s)
    return s or "unknown"


def _ensure_dirs(account_number: str) -> Tuple[Path, Path, Path]:
    """
    Create output directory structure for an account.
    Returns (account_dir, raw_dir, processed_dir).
    """
    account_dir  = BASE_OUTPUT / account_number
    raw_dir      = account_dir / "raw"
    processed_dir = account_dir / "processed"

    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    return account_dir, raw_dir, processed_dir


def _write_csv_and_excel(df: pd.DataFrame, processed_dir: Path, stem: str) -> None:
    """Write a DataFrame as both CSV and Excel."""
    csv_path   = processed_dir / f"{stem}.csv"
    excel_path = processed_dir / f"{stem}.xlsx"

    df.to_csv(csv_path,   index=False, encoding="utf-8-sig")   # utf-8-sig for Excel Thai compat
    df.to_excel(excel_path, index=False, engine="openpyxl")

    logger.info(f"  Exported: {csv_path.name} + {excel_path.name}")


def _reorder_columns(df: pd.DataFrame, preferred_columns: list[str]) -> pd.DataFrame:
    """Return a copy with preferred columns first and any extras preserved."""
    available = [c for c in preferred_columns if c in df.columns]
    extras = [c for c in df.columns if c not in available]
    return df[available + extras].copy()


def _prepare_transaction_exports(transactions: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Build the master transaction table plus deterministic category splits."""
    tx_all = _reorder_columns(transactions, TRANSACTION_EXPORT_COLUMNS).reset_index(drop=True)
    category_frames: dict[str, pd.DataFrame] = {}
    for export_key, rule in TRANSACTION_CATEGORY_RULES.items():
        filtered = tx_all[tx_all["transaction_type"] == rule["transaction_type"]].copy()
        category_frames[export_key] = filtered.reset_index(drop=True)
    return tx_all, category_frames


def _make_entity_label(row: pd.Series) -> str:
    """Return a human-readable entity label for CSV/Excel export."""
    name = str(row.get("name", "") or "").strip()
    account = str(row.get("account_number", "") or "").strip()
    if name and account:
        return f"{name} ({account})"
    return name or account or "UNKNOWN"


def _prepare_entities_export(entities: pd.DataFrame) -> pd.DataFrame:
    """Add i2-friendly identity and label columns to the entity export."""
    if entities.empty:
        return pd.DataFrame(columns=ENTITY_EXPORT_COLUMNS)

    prepared = entities.copy()
    prepared["entity_label"] = prepared.apply(_make_entity_label, axis=1)
    prepared["identity_value"] = prepared.apply(
        lambda row: str(row.get("account_number", "") or "").strip()
        or str(row.get("name", "") or "").strip()
        or "UNKNOWN",
        axis=1,
    )
    return _reorder_columns(prepared, ENTITY_EXPORT_COLUMNS).reset_index(drop=True)


def _resolve_entity_lookup_key(value: str) -> str:
    """Normalize link account identifiers into the entity-table lookup form."""
    value = str(value or "").strip()
    if value.startswith("PARTIAL:"):
        return value.replace("PARTIAL:", "", 1)
    return value or "UNKNOWN"


def _prepare_links_export(links: pd.DataFrame, entities: pd.DataFrame, transactions: pd.DataFrame) -> pd.DataFrame:
    """Add entity references and labels to links for direct graph import use."""
    if links.empty:
        return pd.DataFrame(columns=LINK_EXPORT_COLUMNS)

    entity_by_identity: dict[str, dict] = {}
    for _, row in entities.iterrows():
        identity = str(row.get("identity_value", "") or "").strip()
        if identity:
            entity_by_identity[identity] = row.to_dict()

    txn_details = transactions[[
        c for c in ["transaction_id", "direction", "currency", "counterparty_name", "description"]
        if c in transactions.columns
    ]].copy()
    merged = links.merge(txn_details, how="left", on="transaction_id")

    def map_entity(value: object) -> tuple[str, str]:
        identity = _resolve_entity_lookup_key(str(value or ""))
        entity = entity_by_identity.get(identity, {})
        entity_id = str(entity.get("entity_id", "") or "")
        label = str(entity.get("entity_label", "") or identity or "UNKNOWN")
        return entity_id, label

    from_refs = merged["from_account"].map(map_entity)
    to_refs = merged["to_account"].map(map_entity)

    prepared = merged.copy()
    prepared["link_id"] = prepared.get("transaction_id", "").map(lambda v: f"LNK-{v}" if v else "")
    prepared["from_entity_id"] = [entity_id for entity_id, _ in from_refs]
    prepared["from_label"] = [label for _, label in from_refs]
    prepared["to_entity_id"] = [entity_id for entity_id, _ in to_refs]
    prepared["to_label"] = [label for _, label in to_refs]

    return _reorder_columns(prepared, LINK_EXPORT_COLUMNS).reset_index(drop=True)


def _write_transactions_multisheet(
    transactions: pd.DataFrame,
    transaction_categories: dict[str, pd.DataFrame],
    entities: pd.DataFrame,
    links: pd.DataFrame,
    processed_dir: Path,
    report_filename: str = "report.xlsx",
) -> Path:
    """Write transactions Excel with i2-friendly category sheets + entities + links.

    Returns the Path to the written Excel file.
    """
    excel_path = processed_dir / report_filename

    sheet_map = {
        "All_Transactions": transactions,
        "Transfer_In": transaction_categories["transfer_in"],
        "Transfer_Out": transaction_categories["transfer_out"],
        "Deposits": transaction_categories["deposit"],
        "Withdrawals": transaction_categories["withdraw"],
        "Entities":     entities,
        "Links":        links,
    }

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        for sheet_name, df in sheet_map.items():
            df_clean = df.reset_index(drop=True)
            df_clean.to_excel(writer, sheet_name=sheet_name, index=False)

            # Auto-fit column widths
            ws = writer.sheets[sheet_name]
            for col_cells in ws.columns:
                max_len = max(
                    (len(str(cell.value)) for cell in col_cells if cell.value is not None),
                    default=8,
                )
                col_letter = col_cells[0].column_letter
                ws.column_dimensions[col_letter].width = min(max_len + 2, 40)

    logger.info(f"  Multi-sheet report: {excel_path.name} ({len(sheet_map)} sheets)")
    return excel_path


def export_package(
    transactions: pd.DataFrame,
    entities: pd.DataFrame,
    links: pd.DataFrame,
    account_number: str,
    bank: str,
    original_file: Union[str, Path],
    subject_name: str = "",
    job_id: Optional[str] = None,
) -> Path:
    """
    Export the full Account Package to disk.

    Parameters
    ----------
    transactions   : processed transaction DataFrame
    entities       : entity DataFrame
    links          : graph links DataFrame
    account_number : subject account number (used as folder name)
    bank           : bank name string
    original_file  : path to original Excel input file
    subject_name   : account holder name (used in report filename)

    Returns
    -------
    Path – path to account output directory
    """
    account_dir, raw_dir, processed_dir = _ensure_dirs(account_number)

    # 1. Copy original file
    orig_path = Path(original_file)
    dest_orig = raw_dir / "original.xlsx"
    try:
        shutil.copy2(orig_path, dest_orig)
        logger.info(f"Copied original: {dest_orig}")
    except Exception as e:
        logger.warning(f"Could not copy original file: {e}")

    # 2. Export transactions CSV (for programmatic access)
    transactions_export, transaction_categories = _prepare_transaction_exports(transactions)
    entities_export = _prepare_entities_export(entities)
    links_export = _prepare_links_export(links, entities_export, transactions_export)

    transactions_export.to_csv(processed_dir / "transactions.csv", index=False, encoding="utf-8-sig")
    logger.info("  Exported: transactions.csv")

    for export_key, df in transaction_categories.items():
        _write_csv_and_excel(df, processed_dir, export_key)

    # 3. Export entities CSV + Excel
    _write_csv_and_excel(entities_export, processed_dir, "entities")

    # 4. Export links CSV
    _write_csv_and_excel(links_export, processed_dir, "links")

    # 4b. Export i2 Analyst's Notebook XML (.anx)
    anx_path = processed_dir / "i2_chart.anx"
    try:
        export_anx(entities, transactions, anx_path)
    except Exception as e:
        logger.warning(f"  ANX export failed (non-fatal): {e}")

    # 5. Multi-sheet report Excel (all sheets in one file)
    #    Filename: {subject_name}_{bank}_report.xlsx  (or report.xlsx if no name)
    if subject_name:
        report_name = f"{_safe_filename(subject_name)}_{_safe_filename(bank)}_report.xlsx"
    else:
        report_name = "report.xlsx"
    report_path = _write_transactions_multisheet(
        transactions_export,
        transaction_categories,
        entities_export,
        links_export,
        processed_dir,
        report_filename=report_name,
    )

    # 7. Build and write meta.json
    meta = _build_meta(transactions, account_number, bank)
    meta["report_filename"] = report_path.name
    meta["category_files"] = {
        "all_transactions": "transactions.csv",
        "transfer_in": "transfer_in.csv",
        "transfer_out": "transfer_out.csv",
        "deposit": "deposit.csv",
        "withdraw": "withdraw.csv",
        "entities": "entities.csv",
        "links": "links.csv",
        "anx": "i2_chart.anx",
    }
    meta["category_counts"] = {
        "transfer_in": len(transaction_categories["transfer_in"]),
        "transfer_out": len(transaction_categories["transfer_out"]),
        "deposit": len(transaction_categories["deposit"]),
        "withdraw": len(transaction_categories["withdraw"]),
    }
    meta_path = account_dir / "meta.json"
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"  Meta written: {meta_path}")

    # Write JobMeta row to DB (non-fatal if DB unavailable)
    _write_job_meta_to_db(job_id, account_number, meta)

    logger.info(f"Account package complete: {account_dir}")
    return account_dir


def _write_job_meta_to_db(job_id: Optional[str], account_number: str, meta: dict) -> None:
    """Insert a JobMeta row into the SQLite DB. No-op if job_id is None or DB fails."""
    if not job_id:
        return
    try:
        from database import get_session, JobMeta
        from datetime import datetime as _dt
        with get_session() as session:
            row = JobMeta(
                account_number=account_number,
                job_id=job_id,
                bank=meta.get("bank", ""),
                total_in=float(meta.get("total_in", 0.0)),
                total_out=float(meta.get("total_out", 0.0)),
                total_circulation=float(meta.get("total_circulation", 0.0)),
                num_transactions=int(meta.get("num_transactions", 0)),
                date_range=meta.get("date_range", ""),
                num_unknown=int(meta.get("num_unknown", 0)),
                num_partial_accounts=int(meta.get("num_partial_accounts", 0)),
                report_filename=meta.get("report_filename", ""),
                created_at=_dt.utcnow(),
            )
            session.add(row)
            session.commit()
        logger.info(f"  JobMeta written to DB for job_id={job_id}")
    except Exception as e:
        logger.warning(f"  Could not write JobMeta to DB (non-fatal): {e}")


def _build_meta(transactions: pd.DataFrame, account_number: str, bank: str) -> dict:
    """Compute summary statistics for meta.json."""
    if transactions.empty:
        return {
            "account_number": account_number,
            "bank": bank,
            "total_in": 0,
            "total_out": 0,
            "num_transactions": 0,
            "date_range": "",
            "num_unknown": 0,
            "num_partial_accounts": 0,
        }

    amounts  = transactions["amount"].fillna(0)
    total_in  = float(amounts[amounts > 0].sum())
    total_out = float(amounts[amounts < 0].sum())

    raw_dates = transactions["date"].dropna().tolist()
    date_range = format_date_range(raw_dates) if raw_dates else ""

    if "counterparty_account" in transactions.columns:
        num_unknown = int((transactions["counterparty_account"] == "").sum())
    else:
        num_unknown = 0
    if "partial_account" in transactions.columns:
        num_partial = int((transactions["partial_account"] != "").sum())
    else:
        num_partial = 0

    total_circulation = round(total_in + abs(total_out), 2)

    return {
        "account_number":      account_number,
        "bank":                bank,
        "total_in":            round(total_in, 2),
        "total_out":           round(total_out, 2),
        "total_circulation":   total_circulation,
        "num_transactions":    len(transactions),
        "date_range":          date_range,
        "num_unknown":         num_unknown,
        "num_partial_accounts": num_partial,
    }
