import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import pandas as pd

from core.bulk_processor import _select_bulk_confirmed_mapping, process_folder


def _write_sample_statement(path: Path) -> None:
    df = pd.DataFrame([
        ["เลขที่บัญชี", "1234567890", "", ""],
        ["ชื่อบัญชี", "นาย ตัวอย่าง", "", ""],
        ["วันที่", "รายการ", "จำนวนเงิน", "ยอดคงเหลือ"],
        ["2026-03-01", "ฝากเงิน", "100.00", "100.00"],
    ])
    df.to_excel(path, index=False, header=False, engine="openpyxl")


@contextmanager
def _fake_db_session():
    yield object()


def test_process_folder_writes_case_summary(tmp_path):
    folder = tmp_path / "case"
    folder.mkdir()
    statement = folder / "sample statement.xlsx"
    _write_sample_statement(statement)

    output_root = tmp_path / "output"
    output_root.mkdir()

    fake_output = output_root / "1234567890"
    fake_output.mkdir(parents=True)
    (fake_output / "meta.json").write_text(
        json.dumps({
            "num_transactions": 1,
            "date_range": "2026-03-01",
            "reconciliation": {"status": "VERIFIED", "mismatched_rows": 0},
        }),
        encoding="utf-8",
    )

    with patch("core.bulk_processor.OUTPUT_DIR", output_root), \
         patch("core.bulk_processor.detect_bank", return_value={
             "config_key": "scb",
             "bank": "SCB",
             "confidence": 0.95,
             "ambiguous": False,
         }), \
         patch("core.bulk_processor.find_matching_profile", return_value=None), \
         patch("core.bulk_processor.find_matching_template_variant", return_value=None), \
         patch("core.bulk_processor.get_db_session", side_effect=_fake_db_session), \
         patch("core.bulk_processor.persist_upload", return_value={"file_id": "FILE-1", "duplicate_file_status": "unique"}), \
         patch("core.bulk_processor.create_parser_run", return_value={"parser_run_id": "RUN-1"}), \
         patch("core.bulk_processor.process_account", return_value=fake_output):
        summary = process_folder(folder)

    run_dir = Path(summary["run_dir"])
    assert summary["processed_files"] == 1
    assert summary["skipped_files"] == 0
    assert summary["review_required_files"] == 0
    assert summary["total_transactions"] == 1
    assert summary["total_reconciliation_mismatches"] == 0
    assert summary["bank_counts"]["SCB"] == 1
    assert summary["reconciliation_counts"]["VERIFIED"] == 1
    assert (run_dir / "bulk_summary.csv").exists()
    assert (run_dir / "bulk_summary.xlsx").exists()
    assert (run_dir / "bulk_summary.json").exists()
    assert (run_dir / "case_manifest.json").exists()
    assert (run_dir / "case_bundle.zip").exists()
    assert (run_dir / "case_analytics.json").exists()
    assert (run_dir / "case_analytics.xlsx").exists()
    assert summary["bundle_filename"] == "case_bundle.zip"
    assert summary["manifest_filename"] == "case_manifest.json"
    assert summary["analytics_filename"] == "case_analytics.json"
    assert summary["analytics_workbook_filename"] == "case_analytics.xlsx"
    assert summary["analytics"]["overview"]["processed_accounts"] == 1

    rows = pd.read_csv(run_dir / "bulk_summary.csv", dtype=str).fillna("")
    assert rows.loc[0, "account"] == "1234567890"
    assert rows.loc[0, "reconciliation_status"] == "VERIFIED"

    manifest = json.loads((run_dir / "case_manifest.json").read_text(encoding="utf-8"))
    assert manifest["overview"]["processed_files"] == 1
    assert manifest["generated_outputs"]["case_analytics_json"] == "case_analytics.json"
    assert manifest["accounts"][0]["account"] == "1234567890"
    assert manifest["accounts"][0]["mapping_suggestion_source"] == "auto"
    assert manifest["accounts"][0]["template_variant_match"] is None
    assert manifest["accounts"][0]["needs_review"] is False

    with ZipFile(run_dir / "case_bundle.zip") as bundle:
        names = set(bundle.namelist())
    assert "bulk_summary.csv" in names
    assert "bulk_summary.xlsx" in names
    assert "bulk_summary.json" in names
    assert "case_manifest.json" in names
    assert "case_analytics.json" in names
    assert "case_analytics.xlsx" in names


def test_bulk_mapping_uses_only_trusted_template_variants():
    df = pd.DataFrame(
        [["2026-03-01", "รับโอน", "", "100", "100"]],
        columns=["วันที่", "รายการ", "ถอนเงิน", "เงินฝาก", "ยอดคงเหลือ"],
    )
    detection = {"config_key": "scb", "key": "scb", "bank": "SCB", "confidence": 0.95, "ambiguous": False}
    column_detection = {
        "suggested_mapping": {
            "date": "วันที่",
            "description": "รายการ",
            "amount": "ยอดคงเหลือ",
        }
    }
    trusted_variant = {
        "variant_id": "VARIANT-TRUSTED",
        "bank_key": "scb",
        "trust_state": "trusted",
        "match_type": "ordered_signature",
        "match_score": 1.0,
        "confirmation_count": 3,
        "correction_count": 0,
        "reviewer_count": 2,
        "confirmed_mapping": {
            "date": "วันที่",
            "description": "รายการ",
            "debit": "ถอนเงิน",
            "credit": "เงินฝาก",
            "balance": "ยอดคงเหลือ",
        },
    }

    with (
        patch("core.bulk_processor.find_matching_profile", return_value=None),
        patch("core.bulk_processor.find_matching_template_variant", return_value=trusted_variant) as find_variant,
        patch("core.bulk_processor.get_db_session", side_effect=_fake_db_session),
    ):
        mapping_context = _select_bulk_confirmed_mapping(
            df,
            detection,
            column_detection,
            source_type="excel",
            sheet_name="Sheet1",
            header_row=0,
        )

    assert mapping_context["suggestion_source"] == "template_variant"
    assert mapping_context["template_variant_match"]["variant_id"] == "VARIANT-TRUSTED"
    assert mapping_context["template_variant_match"]["auto_pass_eligible"] is False
    assert mapping_context["template_variant_match"]["auto_pass_gate"]["mode"] == "observe_only"
    assert "no_valid_preview_rows" in mapping_context["template_variant_match"]["auto_pass_gate"]["blocked_reasons"]
    assert mapping_context["confirmed_mapping"]["amount"] is None
    assert mapping_context["confirmed_mapping"]["debit"] == "ถอนเงิน"
    assert mapping_context["confirmed_mapping"]["credit"] == "เงินฝาก"
    find_variant.assert_called_once()
    assert find_variant.call_args.kwargs["include_candidate"] is False
    assert find_variant.call_args.kwargs["allowed_trust_states"] == {"trusted"}
