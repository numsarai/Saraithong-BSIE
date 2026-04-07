"""Regression tests for weighted bank auto-detection."""
import json
from pathlib import Path

import pandas as pd
import pytest

from core.autodetect import analyze_file
from core.bank_detector import detect_bank
from core.loader import find_best_sheet_and_header, load_config, load_excel
from core.normalizer import normalize


def _skip_if_missing(paths: list[Path], label: str) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        pytest.skip(f"{label} not available in this checkout: {', '.join(missing)}")


def test_detect_bank_identifies_scb_dual_account_headers():
    df = pd.DataFrame(columns=[
        "วันที่", "เวลา", "รายการ", "ถอนเงิน", "เงินฝาก",
        "จำนวนเงินคงเหลือ", "บัญชีผู้โอน", "ชื่อผู้โอน",
        "บัญชีผู้รับโอน", "ชื่อผู้รับโอน",
    ])

    result = detect_bank(df, extra_text="scb_statement.xlsx Sheet1")

    assert result["config_key"] == "scb"
    assert result["bank"] == "SCB"
    assert result["score"] > 10
    assert result["confidence"] >= 0.8
    assert result["ambiguous"] is False
    assert any("strong_header:บัญชีผู้โอน" in item for item in result["evidence"]["positive"])


def test_detect_bank_identifies_kbank_dual_account_headers():
    df = pd.DataFrame(columns=[
        "วันที่ทำรายการ", "เวลาที่ทำรายการ", "ประเภทรายการ", "ช่องทาง",
        "หมายเลขบัญชีต้นทาง", "ชื่อบัญชีต้นทาง",
        "หมายเลขบัญชีปลายทาง", "ชื่อบัญชีปลายทาง",
        "ถอนเงิน", "ฝากเงิน", "ยอดเงินคงเหลือ",
    ])

    result = detect_bank(df, extra_text="kbank_export.xlsx transactions")

    assert result["config_key"] == "kbank"
    assert result["bank"] == "KBANK"
    assert result["confidence"] >= 0.8
    assert result["top_candidates"][0] == "kbank"


def test_detect_bank_identifies_ktb_transfer_layout():
    df = pd.DataFrame(columns=[
        "วันที่ทำรายการ", "เวลา", "รายละเอียด", "จำนวนเงิน",
        "ธนาคารผู้โอน", "เลขที่บัญชีผู้โอน", "ชื่อผู้โอน",
        "ธนาคารผู้รับโอน", "เลขที่บัญชีผู้รับโอน", "ชื่อผู้รับโอน",
    ])

    result = detect_bank(df, extra_text="ktb_transfer_log.xlsx transfers")

    assert result["config_key"] == "ktb"
    assert result["bank"] == "KTB"
    assert result["confidence"] >= 0.8
    assert "ktb" in result["top_candidates"]


def test_detect_bank_marks_generic_headers_as_ambiguous():
    df = pd.DataFrame(columns=["วันที่ทำรายการ", "เวลา", "รายละเอียด", "จำนวนเงิน", "ยอดคงเหลือ"])

    result = detect_bank(df, extra_text="statement.xlsx")

    assert result["config_key"] == "generic"
    assert result["bank"] == "UNKNOWN"
    assert result["ambiguous"] is True
    assert result["confidence"] <= 0.55
    assert len(result["top_candidates"]) >= 2


def test_analyze_file_uses_weighted_bank_detection(tmp_path):
    sheet_df = pd.DataFrame([
        ["วันที่", "เวลา", "รายการ", "ถอนเงิน", "เงินฝาก", "จำนวนเงินคงเหลือ", "บัญชีผู้โอน", "ชื่อผู้โอน", "บัญชีผู้รับโอน", "ชื่อผู้รับโอน"],
        ["2026-03-01", "10:00", "โอนเงิน", "", "100.00", "1000.00", "1111111111", "นาย ก", "2222222222", "นาย ข"],
    ])
    workbook = tmp_path / "scb_sample.xlsx"
    sheet_df.to_excel(workbook, header=False, index=False)

    result = analyze_file(str(workbook), configs={})

    assert result["detected_bank"] == "scb"


def test_load_config_prefers_custom_override(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    builtin_dir = tmp_path / "builtin"
    config_dir.mkdir()
    builtin_dir.mkdir()

    (config_dir / "kbank.json").write_text(
        json.dumps({"bank_name": "KBANK CUSTOM", "header_row": 7}),
        encoding="utf-8",
    )
    (builtin_dir / "kbank.json").write_text(
        json.dumps({"bank_name": "KBANK BUILTIN", "header_row": 0}),
        encoding="utf-8",
    )

    monkeypatch.setattr("core.loader.CONFIG_DIR", config_dir)
    monkeypatch.setattr("core.loader.BUILTIN_CONFIG_DIR", builtin_dir)

    cfg = load_config("kbank")

    assert cfg["bank_name"] == "KBANK CUSTOM"
    assert cfg["header_row"] == 7


def test_load_config_falls_back_to_builtin_when_user_config_missing(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    builtin_dir = tmp_path / "builtin"
    config_dir.mkdir()
    builtin_dir.mkdir()

    (builtin_dir / "kbank.json").write_text(
        json.dumps({"bank_name": "KBANK BUILTIN", "header_row": 1}),
        encoding="utf-8",
    )

    monkeypatch.setattr("core.loader.CONFIG_DIR", config_dir)
    monkeypatch.setattr("core.loader.BUILTIN_CONFIG_DIR", builtin_dir)

    cfg = load_config("kbank")

    assert cfg["bank_name"] == "KBANK BUILTIN"
    assert cfg["header_row"] == 1


def test_detect_bank_matches_real_sample_workbooks():
    sample_dir = Path("data/sample_statements")
    expectations = {
        "sample_01_kbank.xlsx": "kbank",
        "sample_02_scb.xlsx": "scb",
        "sample_03_ktb.xlsx": "ktb",
        "sample_04_bbl.xlsx": "bbl",
        "sample_05_bay.xlsx": "bay",
        "sample_06_ttb.xlsx": "ttb",
        "sample_07_gsb.xlsx": "gsb",
        "sample_08_kbank_en.xlsx": "kbank",
        "sample_09_scb_savings.xlsx": "scb",
    }
    _skip_if_missing([sample_dir / filename for filename in expectations], "golden sample workbooks")

    for filename, expected_key in expectations.items():
        path = sample_dir / filename
        xf = pd.ExcelFile(path, engine="openpyxl")
        preview = pd.read_excel(path, sheet_name=xf.sheet_names[0], header=None, nrows=40, dtype=str).fillna("")
        result = detect_bank(preview, extra_text=f"{path.stem} {xf.sheet_names[0]}")
        assert result["config_key"] == expected_key, f"{filename} detected as {result['config_key']}"


def test_detect_bank_marks_real_messy_sample_as_generic():
    path = Path("data/sample_statements/sample_10_mixed_messy.xlsx")
    _skip_if_missing([path], "messy sample workbook")
    xf = pd.ExcelFile(path, engine="openpyxl")
    preview = pd.read_excel(path, sheet_name=xf.sheet_names[0], header=None, nrows=40, dtype=str).fillna("")

    result = detect_bank(preview, extra_text=f"{path.stem} {xf.sheet_names[0]}")

    assert result["config_key"] == "generic"
    assert result["bank"] == "UNKNOWN"
    assert result["ambiguous"] is True


def test_find_best_sheet_and_header_skips_empty_cover_sheet_on_real_scb_workbook():
    path = Path("ตัวอย่างไฟล์ธนาคาร/ตัวอย่าง ไทยพาณิชย์ 68058421-6302541889 นาย กฤตกร เพิ่มพูล.xlsx")
    _skip_if_missing([path], "attached SCB workbook")

    pick = find_best_sheet_and_header(path)

    assert pick["sheet_name"] != "Sheet1"
    assert "6302541889" in pick["sheet_name"]
    assert int(pick["header_row"]) in {0, 1}


def test_detect_bank_matches_attached_real_workbooks():
    real_dir = Path("ตัวอย่างไฟล์ธนาคาร")
    expectations = {
        "scb 7882476275 นาย ทวีกิจ แก้วฤทธิ์.xlsx": "scb",
        "stm  วรุตม์.xlsx": "ciaf",
        "ตัวอย่าง  กรุงไทย 9813389540  น.ส.อรอุมา อินทองปาน.xlsx": "ktb",
        "ตัวอย่าง กรุงศรี A-002-6941230651-EStatement.xlsx": "bay",
        "ตัวอย่าง กรุงไทย 1.xlsx": "ktb",
        "ตัวอย่าง กสิกรไทย 1.xlsx": "kbank",
        "ตัวอย่าง ไทยพาณิชย์ 1.xlsx": "scb",
        "ตัวอย่าง ไทยพาณิชย์ 68058421-6302541889 นาย กฤตกร เพิ่มพูล.xlsx": "scb",
        "ตัวอย่าง ไทยพาณิชย์ 68058421-8112726972 นาย นราพล บุญแก้ว.xlsx": "scb",
    }
    _skip_if_missing([real_dir / filename for filename in expectations], "attached real workbooks")

    for filename, expected_key in expectations.items():
        path = real_dir / filename
        pick = find_best_sheet_and_header(path, preview_rows=40, scan_rows=15)
        df = pd.read_excel(path, sheet_name=pick["sheet_name"], header=pick["header_row"], dtype=str).dropna(how="all")
        df.columns = [str(col).strip() for col in df.columns]
        result = detect_bank(df, extra_text=f"{path.stem} {pick['sheet_name']}")
        assert result["config_key"] == expected_key, f"{filename} detected as {result['config_key']}"


def test_normalize_real_bay_direction_marker_workbook():
    path = Path("ตัวอย่างไฟล์ธนาคาร/ตัวอย่าง กรุงศรี A-002-6941230651-EStatement.xlsx")
    _skip_if_missing([path], "attached BAY workbook")

    cfg = load_config("bay")
    raw_df = load_excel(path, cfg)
    norm_df = normalize(raw_df, cfg, subject_account="6941230651", subject_name="MR. KORT THANTHAVONGSA")

    assert not norm_df.empty
    assert {"IN", "OUT"} <= set(norm_df["direction"].dropna().unique())

    first_in = norm_df[norm_df["direction"] == "IN"].iloc[0]
    first_out = norm_df[norm_df["direction"] == "OUT"].iloc[0]
    assert first_in["amount"] > 0
    assert first_out["amount"] < 0


def test_normalize_real_ciaf_export_workbook():
    path = Path("ตัวอย่างไฟล์ธนาคาร/stm  วรุตม์.xlsx")
    _skip_if_missing([path], "attached CIAF workbook")

    cfg = load_config("ciaf")
    raw_df = load_excel(path, cfg)
    norm_df = normalize(raw_df, cfg, subject_account="9249452112", subject_name="นาย วิวัฒน์ ศรีสมรูป")

    assert not norm_df.empty
    assert {"IN", "OUT"} <= set(norm_df["direction"].dropna().unique())
    assert any(acc == "1621583030" for acc in norm_df["counterparty_account"].fillna(""))
