"""
bulk_processor.py
-----------------
Case-level folder intake for multiple statement files.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd

from core.bank_detector import detect_bank
from core.case_analytics import compute_case_analytics, write_case_analytics
from core.column_detector import detect_columns
from core.loader import find_best_sheet_and_header
from core.mapping_memory import find_matching_profile
from core.subject_inference import infer_subject_identity
from pipeline.process_account import process_account
from paths import OUTPUT_DIR
from services.file_ingestion_service import persist_upload
from services.persistence_pipeline_service import create_parser_run

logger = logging.getLogger(__name__)


def process_folder(folder_path: str | Path, recursive: bool = False, operator: str = "bulk-intake") -> dict[str, Any]:
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        raise FileNotFoundError(f"Folder not found: {folder}")

    file_paths = _collect_input_files(folder, recursive=recursive)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = OUTPUT_DIR / "bulk_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for file_path in file_paths:
        results.append(_process_single_file(file_path, operator=operator))

    summary = _build_summary(folder, run_id, results)
    summary_df = pd.DataFrame(results)
    summary_df.to_csv(run_dir / "bulk_summary.csv", index=False, encoding="utf-8-sig")
    summary_df.to_excel(run_dir / "bulk_summary.xlsx", index=False, engine="openpyxl")
    analytics = compute_case_analytics(summary)
    write_case_analytics(run_dir, analytics)
    summary["analytics_filename"] = "case_analytics.json"
    summary["analytics_workbook_filename"] = "case_analytics.xlsx"
    summary["analytics"] = analytics
    summary["analytics_overview"] = analytics.get("overview", {})
    (run_dir / "bulk_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    summary["bundle_filename"] = "case_bundle.zip"
    summary["manifest_filename"] = "case_manifest.json"
    manifest = _build_case_manifest(summary)
    manifest_path = run_dir / "case_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    bundle_path = _build_case_bundle(run_dir, results)
    summary["bundle_filename"] = bundle_path.name
    summary["manifest_filename"] = manifest_path.name

    summary["run_dir"] = str(run_dir)
    return summary


def _collect_input_files(folder: Path, recursive: bool) -> list[Path]:
    patterns = ("*.xlsx", "*.xls", "*.ofx", "*.pdf", "*.png", "*.jpg", "*.jpeg", "*.bmp")
    files: list[Path] = []
    for pattern in patterns:
        if recursive:
            files.extend(folder.rglob(pattern))
        else:
            files.extend(folder.glob(pattern))
    return sorted({path for path in files if path.is_file()})


def _process_single_file(file_path: Path, operator: str = "bulk-intake") -> dict[str, Any]:
    record: dict[str, Any] = {
        "file_name": file_path.name,
        "file_path": str(file_path),
        "status": "pending",
        "account": "",
        "name": "",
        "bank_key": "",
        "bank_name": "",
        "output_dir": "",
        "job_error": "",
    }

    try:
        if file_path.suffix.lower() == ".ofx":
            from core.ofx_io import infer_identity_from_ofx, parse_ofx_file

            ofx_preview = parse_ofx_file(file_path)
            inferred = infer_identity_from_ofx(file_path, ofx_preview)
            record["account"] = inferred.get("account", "")
            record["name"] = inferred.get("name", "")
            record["sheet_name"] = "OFX"
            record["header_row"] = 0
            data_df = ofx_preview.head(100).copy()
            detection = {
                "config_key": "ofx",
                "bank": "OFX",
                "confidence": 1.0,
                "ambiguous": False,
            }
            confirmed_mapping = {}
        elif file_path.suffix.lower() == ".pdf":
            from core.pdf_loader import parse_pdf_file
            from core.image_loader import parse_image_file

            pdf_result = parse_pdf_file(file_path)
            if pdf_result["tables_found"] == 0 or len(pdf_result["df"]) < 3:
                pdf_result = parse_image_file(file_path)
            data_df = pdf_result["df"]
            if data_df.empty:
                record["status"] = "skipped"
                record["job_error"] = "Could not extract a transaction table from this PDF."
                return record
            data_df.columns = [str(c).strip() for c in data_df.columns]
            identity = infer_subject_identity(file_path, preview_df=data_df.head(15))
            record["account"] = identity["account"]
            record["name"] = identity["name"]
            record["sheet_name"] = pdf_result["source_format"]
            record["header_row"] = int(pdf_result.get("header_row", 0))
            if not record["account"]:
                record["status"] = "skipped"
                record["job_error"] = "Could not infer subject account from PDF content."
                return record
            detection = detect_bank(data_df, extra_text=file_path.stem, sheet_name=record["sheet_name"])
            column_detection = detect_columns(data_df)
            mapping_profile = find_matching_profile(list(data_df.columns), bank=detection.get("config_key", ""))
            confirmed_mapping = mapping_profile["mapping"] if mapping_profile else column_detection["suggested_mapping"]
        elif file_path.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp"):
            from core.image_loader import parse_image_file

            img_result = parse_image_file(file_path)
            data_df = img_result["df"]
            if data_df.empty:
                record["status"] = "skipped"
                record["job_error"] = "Could not extract a transaction table from this image."
                return record
            data_df.columns = [str(c).strip() for c in data_df.columns]
            identity = infer_subject_identity(file_path, preview_df=data_df.head(15))
            record["account"] = identity["account"]
            record["name"] = identity["name"]
            record["sheet_name"] = "IMAGE"
            record["header_row"] = int(img_result.get("header_row", 0))
            if not record["account"]:
                record["status"] = "skipped"
                record["job_error"] = "Could not infer subject account from image."
                return record
            detection = detect_bank(data_df, extra_text=file_path.stem, sheet_name="IMAGE")
            column_detection = detect_columns(data_df)
            mapping_profile = find_matching_profile(list(data_df.columns), bank=detection.get("config_key", ""))
            confirmed_mapping = mapping_profile["mapping"] if mapping_profile else column_detection["suggested_mapping"]
        else:
            sheet_pick = find_best_sheet_and_header(file_path)
            preview_df = sheet_pick["preview_df"]
            identity = infer_subject_identity(file_path, preview_df=preview_df)
            record["account"] = identity["account"]
            record["name"] = identity["name"]
            record["sheet_name"] = sheet_pick["sheet_name"]
            record["header_row"] = int(sheet_pick["header_row"])

            if not record["account"]:
                record["status"] = "skipped"
                record["job_error"] = "Could not infer subject account from filename or workbook header."
                return record

            data_df = pd.read_excel(
                file_path,
                sheet_name=record["sheet_name"],
                header=record["header_row"],
                dtype=str,
                engine="openpyxl",
            ).dropna(how="all")
            data_df.columns = [str(column).strip() for column in data_df.columns]

            detection = detect_bank(
                data_df,
                extra_text=f"{file_path.stem} {record['sheet_name']}",
                sheet_name=str(record["sheet_name"] or ""),
            )
        record["bank_key"] = detection.get("config_key", "") or "generic"
        record["bank_name"] = detection.get("bank", "")
        record["bank_confidence"] = detection.get("confidence", 0.0)
        record["bank_ambiguous"] = bool(detection.get("ambiguous", False))

        if file_path.suffix.lower() != ".ofx":
            column_detection = detect_columns(data_df)
            mapping_profile = find_matching_profile(list(data_df.columns), bank=record["bank_key"])
            confirmed_mapping = mapping_profile["mapping"] if mapping_profile else column_detection["suggested_mapping"]

        upload_meta = persist_upload(
            content=file_path.read_bytes(),
            original_filename=file_path.name,
            uploaded_by=operator or "bulk-intake",
            mime_type=None,
        )
        parser_run = create_parser_run(
            file_id=upload_meta["file_id"],
            bank_detected=record["bank_key"],
            confirmed_mapping=confirmed_mapping,
            operator=operator or "bulk-intake",
        )
        record["file_id"] = upload_meta["file_id"]
        record["parser_run_id"] = parser_run["parser_run_id"]
        record["duplicate_file_status"] = upload_meta.get("duplicate_file_status", "unique")

        output_dir = process_account(
            input_file=file_path,
            subject_account=record["account"],
            subject_name=record["name"],
            bank_key=record["bank_key"],
            confirmed_mapping=confirmed_mapping,
            file_id=record["file_id"],
            parser_run_id=record["parser_run_id"],
            operator=operator or "bulk-intake",
        )
        record["output_dir"] = str(output_dir)
        record["status"] = "processed"

        meta_path = output_dir / "meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            reconciliation = meta.get("reconciliation") or {}
            record["num_transactions"] = meta.get("num_transactions", 0)
            record["date_range"] = meta.get("date_range", "")
            record["reconciliation_status"] = reconciliation.get("status", "")
            record["reconciliation_mismatches"] = reconciliation.get("mismatched_rows", 0)
            record["chronology_issue_detected"] = bool(reconciliation.get("chronology_issue_detected", False))
            record["chronological_mismatched_rows"] = int(reconciliation.get("chronological_mismatched_rows", 0) or 0)
            record["mismatches_reduced_by_sorting"] = int(reconciliation.get("mismatches_reduced_by_sorting", 0) or 0)
            record["rounding_drift_rows"] = int(reconciliation.get("rounding_drift_rows", 0) or 0)
            record["material_mismatched_rows"] = int(reconciliation.get("material_mismatched_rows", 0) or 0)
            record["missing_time_rows"] = int(reconciliation.get("missing_time_rows", 0) or 0)
            record["duplicate_timestamp_rows"] = int(reconciliation.get("duplicate_timestamp_rows", 0) or 0)
            record["recommended_check_mode"] = reconciliation.get("recommended_check_mode", "file_order")
            record["suspected_scenarios"] = list(reconciliation.get("suspected_scenarios", []) or [])
        return record
    except Exception as exc:
        logger.exception("Bulk intake failed for %s: %s", file_path.name, exc)
        record["status"] = "error"
        record["job_error"] = str(exc)
        return record


def _build_summary(folder: Path, run_id: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    processed = [row for row in results if row["status"] == "processed"]
    skipped = [row for row in results if row["status"] == "skipped"]
    errored = [row for row in results if row["status"] == "error"]
    review_required = [
        row for row in processed
        if _needs_analyst_review(row)
    ]
    reconciliation_counts = {
        status: sum(1 for row in processed if row.get("reconciliation_status") == status)
        for status in ("VERIFIED", "PARTIAL", "FAILED", "INFERRED", "")
    }
    reconciliation_counts["UNKNOWN"] = reconciliation_counts.pop("")

    bank_counts: dict[str, int] = {}
    for row in processed:
        label = str(row.get("bank_name") or row.get("bank_key") or "UNKNOWN")
        bank_counts[label] = bank_counts.get(label, 0) + 1

    total_transactions = int(sum(int(row.get("num_transactions") or 0) for row in processed))
    total_reconciliation_mismatches = int(sum(int(row.get("reconciliation_mismatches") or 0) for row in processed))
    chronology_issue_files = int(sum(1 for row in processed if row.get("chronology_issue_detected")))
    drift_issue_files = int(sum(1 for row in processed if int(row.get("rounding_drift_rows") or 0) > 0))
    material_mismatch_files = int(sum(1 for row in processed if int(row.get("material_mismatched_rows") or 0) > 0))

    return {
        "run_id": run_id,
        "folder": str(folder),
        "total_files": len(results),
        "processed_files": len(processed),
        "skipped_files": len(skipped),
        "error_files": len(errored),
        "review_required_files": len(review_required),
        "total_transactions": total_transactions,
        "total_reconciliation_mismatches": total_reconciliation_mismatches,
        "chronology_issue_files": chronology_issue_files,
        "drift_issue_files": drift_issue_files,
        "material_mismatch_files": material_mismatch_files,
        "accounts": sorted({row.get("account", "") for row in processed if row.get("account")}),
        "bank_counts": dict(sorted(bank_counts.items())),
        "reconciliation_counts": reconciliation_counts,
        "analytics_overview": {},
        "files": results,
    }


def _needs_analyst_review(row: dict[str, Any]) -> bool:
    if row.get("status") != "processed":
        return False
    return (
        bool(row.get("bank_ambiguous"))
        or row.get("reconciliation_status") in {"FAILED", "PARTIAL", "INFERRED"}
        or float(row.get("bank_confidence") or 0.0) < 0.75
    )


def _build_case_bundle(run_dir: Path, results: list[dict[str, Any]]) -> Path:
    bundle_path = run_dir / "case_bundle.zip"
    with ZipFile(bundle_path, "w", compression=ZIP_DEFLATED) as zf:
        for summary_name in ("bulk_summary.csv", "bulk_summary.xlsx", "bulk_summary.json", "case_manifest.json"):
            summary_file = run_dir / summary_name
            if summary_file.exists():
                zf.write(summary_file, arcname=summary_name)
        for analytics_name in ("case_analytics.json", "case_analytics.xlsx"):
            analytics_file = run_dir / analytics_name
            if analytics_file.exists():
                zf.write(analytics_file, arcname=analytics_name)

        for row in results:
            if row.get("status") != "processed":
                continue
            output_dir = Path(str(row.get("output_dir") or ""))
            if not output_dir.exists() or not output_dir.is_dir():
                continue
            account_label = str(row.get("account") or output_dir.name or "unknown")
            for file_path in sorted(output_dir.rglob("*")):
                if not file_path.is_file():
                    continue
                relative = file_path.relative_to(output_dir)
                arcname = Path("accounts") / account_label / relative
                zf.write(file_path, arcname=str(arcname))
    return bundle_path


def _build_case_manifest(summary: dict[str, Any]) -> dict[str, Any]:
    files = summary.get("files", [])
    return {
        "case_run_id": summary.get("run_id", ""),
        "source_folder": summary.get("folder", ""),
        "generated_outputs": {
            "bundle": summary.get("bundle_filename", "case_bundle.zip"),
            "bulk_summary_csv": "bulk_summary.csv",
            "bulk_summary_xlsx": "bulk_summary.xlsx",
            "bulk_summary_json": "bulk_summary.json",
            "case_manifest_json": "case_manifest.json",
            "case_analytics_json": summary.get("analytics_filename", "case_analytics.json"),
            "case_analytics_xlsx": summary.get("analytics_workbook_filename", "case_analytics.xlsx"),
        },
        "overview": {
            "total_files": summary.get("total_files", 0),
            "processed_files": summary.get("processed_files", 0),
            "skipped_files": summary.get("skipped_files", 0),
            "error_files": summary.get("error_files", 0),
            "review_required_files": summary.get("review_required_files", 0),
            "total_transactions": summary.get("total_transactions", 0),
            "total_reconciliation_mismatches": summary.get("total_reconciliation_mismatches", 0),
            "chronology_issue_files": summary.get("chronology_issue_files", 0),
            "drift_issue_files": summary.get("drift_issue_files", 0),
            "material_mismatch_files": summary.get("material_mismatch_files", 0),
            "flagged_accounts": ((summary.get("analytics") or {}).get("overview") or {}).get("flagged_accounts", 0),
            "connected_groups": ((summary.get("analytics") or {}).get("overview") or {}).get("connected_groups", 0),
        },
        "bank_distribution": summary.get("bank_counts", {}),
        "reconciliation_distribution": summary.get("reconciliation_counts", {}),
        "analytics_overview": (summary.get("analytics") or {}).get("overview", {}),
        "accounts": [
            {
                "account": row.get("account", ""),
                "name": row.get("name", ""),
                "bank": row.get("bank_name") or row.get("bank_key") or "",
                "status": row.get("status", ""),
                "reconciliation_status": row.get("reconciliation_status", ""),
                "chronology_issue_detected": bool(row.get("chronology_issue_detected")),
                "rounding_drift_rows": int(row.get("rounding_drift_rows") or 0),
                "material_mismatched_rows": int(row.get("material_mismatched_rows") or 0),
                "recommended_check_mode": row.get("recommended_check_mode", "file_order"),
                "needs_review": _needs_analyst_review(row),
                "output_dir": row.get("output_dir", ""),
            }
            for row in files
            if row.get("status") == "processed"
        ],
        "skipped_or_error_files": [
            {
                "file_name": row.get("file_name", ""),
                "status": row.get("status", ""),
                "reason": row.get("job_error", ""),
            }
            for row in files
            if row.get("status") in {"skipped", "error"}
        ],
    }
