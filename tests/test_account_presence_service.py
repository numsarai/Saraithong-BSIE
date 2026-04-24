from pathlib import Path

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
