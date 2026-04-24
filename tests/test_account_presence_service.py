from pathlib import Path
from unittest.mock import patch

import pandas as pd

from services.account_presence_service import verify_account_presence


def test_verify_account_presence_finds_exact_workbook_location(tmp_path: Path):
    workbook = tmp_path / "statement.xlsx"
    pd.DataFrame(
        [
            ["Statement for account 123-456-7890", "", ""],
            ["วันที่", "รายละเอียด", "จำนวนเงิน"],
            ["2026-01-01", "โอนจาก 9999999999", "100.00"],
        ]
    ).to_excel(workbook, header=False, index=False)

    result = verify_account_presence(
        file_path=workbook,
        subject_account="1234567890",
        sheet_name="Sheet1",
        header_row=1,
    )

    assert result["status"] == "ok"
    assert result["found"] is True
    assert result["match_status"] == "exact_found"
    assert result["locations"][0]["row_zone"] == "pre_header"
    assert result["locations"][0]["row_number"] == 1


def test_verify_account_presence_marks_leading_zero_loss_candidate(tmp_path: Path):
    workbook = tmp_path / "leading_zero.xlsx"
    pd.DataFrame(
        [
            ["บัญชี", "รายการ"],
            ["123456789", "Excel lost the leading zero"],
        ]
    ).to_excel(workbook, header=False, index=False)

    result = verify_account_presence(
        file_path=workbook,
        subject_account="0123456789",
        sheet_name="Sheet1",
        header_row=0,
    )

    assert result["found"] is False
    assert result["possible_match"] is True
    assert result["match_status"] == "possible_leading_zero_loss"
    assert result["possible_locations"][0]["match_type"] == "possible_leading_zero_loss"


def test_verify_account_presence_scans_text_pdf_lines(tmp_path: Path):
    from fpdf import FPDF

    pdf_path = tmp_path / "statement.pdf"
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, "Statement account 123-456-7890", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, "Date Description Amount", new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(pdf_path))

    result = verify_account_presence(
        file_path=pdf_path,
        subject_account="1234567890",
    )

    assert result["status"] == "ok"
    assert result["file_type"] == "pdf"
    assert result["found"] is True
    assert result["match_status"] == "exact_found"
    assert result["locations"][0]["source_region"] == "page_text"
    assert result["locations"][0]["page_number"] == 1
    assert result["summary"]["text_lines_scanned"] >= 1


def test_verify_account_presence_scans_image_ocr_table(tmp_path: Path):
    image_path = tmp_path / "statement.png"
    image_path.write_bytes(b"not-a-real-image")
    ocr_df = pd.DataFrame(
        [
            {"Account": "123-456-7890", "Amount": "100.00"},
        ]
    )

    with patch("core.image_loader.parse_image_file", return_value={
        "df": ocr_df,
        "source_format": "IMAGE",
        "page_count": 1,
        "ocr_used": True,
        "header_row": 0,
        "tables_found": 1,
    }):
        result = verify_account_presence(
            file_path=image_path,
            subject_account="1234567890",
        )

    assert result["status"] == "ok"
    assert result["file_type"] == "image_ocr"
    assert result["found"] is True
    assert result["locations"][0]["source_region"] == "ocr_table"
    assert result["locations"][0]["column_label"] == "Account"


def test_verify_account_presence_scans_image_raw_ocr_tokens_when_table_is_empty(tmp_path: Path):
    image_path = tmp_path / "statement.png"
    image_path.write_bytes(b"not-a-real-image")

    with patch("core.image_loader.parse_image_file", return_value={
        "df": pd.DataFrame(),
        "source_format": "IMAGE",
        "page_count": 1,
        "ocr_used": True,
        "header_row": 0,
        "tables_found": 0,
        "ocr_tokens": [
            {
                "text": "Header account 123-456-7890",
                "confidence": 0.91,
                "page_number": 1,
                "x_center": 120.0,
                "y_center": 40.0,
            },
        ],
    }):
        result = verify_account_presence(
            file_path=image_path,
            subject_account="1234567890",
        )

    assert result["status"] == "ok"
    assert result["found"] is True
    assert result["match_status"] == "exact_found"
    assert result["locations"][0]["source_region"] == "ocr_token"
    assert result["locations"][0]["column_label"] == "ocr_token"
    assert result["locations"][0]["ocr_confidence"] == 0.91
    assert result["summary"]["ocr_tokens_scanned"] == 1


def test_verify_account_presence_returns_warning_when_image_ocr_unavailable(tmp_path: Path):
    image_path = tmp_path / "statement.png"
    image_path.write_bytes(b"not-a-real-image")

    with patch("core.image_loader.parse_image_file", side_effect=RuntimeError("EasyOCR missing")):
        result = verify_account_presence(
            file_path=image_path,
            subject_account="1234567890",
        )

    assert result["status"] == "read_error"
    assert result["match_status"] == "read_error"
    assert result["found"] is False
    assert "OCR scan unavailable" in result["warnings"][0]
