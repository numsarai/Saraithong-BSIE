from services.mapping_validation_service import validate_and_preview_mapping, validate_mapping


def test_validate_mapping_accepts_amount_with_direction_marker_preview():
    columns = ["วันที่", "รายละเอียด", "ประเภทรายการ", "จำนวนเงิน", "ยอดคงเหลือ"]
    mapping = {
        "date": "วันที่",
        "description": "รายละเอียด",
        "direction_marker": "ประเภทรายการ",
        "amount": "จำนวนเงิน",
        "balance": "ยอดคงเหลือ",
    }

    result = validate_and_preview_mapping(
        bank="bay",
        mapping=mapping,
        columns=columns,
        sample_rows=[
            {"วันที่": "2026-01-08", "รายละเอียด": "โอนเงินไป", "ประเภทรายการ": "DR", "จำนวนเงิน": "500.00", "ยอดคงเหลือ": "20,500.00"},
            {"วันที่": "2026-01-09", "รายละเอียด": "รับโอนจาก", "ประเภทรายการ": "CR", "จำนวนเงิน": "1,600.00", "ยอดคงเหลือ": "22,100.00"},
        ],
    )

    assert result["ok"] is True
    assert result["amount_mode"] == "direction_marker"
    assert result["dry_run_preview"]["summary"]["valid_transaction_rows"] == 2
    rows = result["dry_run_preview"]["rows"]
    assert rows[0]["amount"] == -500.0
    assert rows[0]["direction"] == "OUT"
    assert rows[0]["source"]["direction_marker"] == "DR"
    assert rows[1]["amount"] == 1600.0
    assert rows[1]["direction"] == "IN"


def test_validate_mapping_rejects_direction_marker_with_debit_credit_conflict():
    result = validate_mapping(
        {
            "date": "วันที่",
            "description": "รายละเอียด",
            "direction_marker": "ประเภทรายการ",
            "amount": "จำนวนเงิน",
            "debit": "ถอนเงิน",
        },
        ["วันที่", "รายละเอียด", "ประเภทรายการ", "จำนวนเงิน", "ถอนเงิน"],
        bank="bay",
    )

    assert result["ok"] is False
    assert any(issue["code"] == "conflicting_amount_paths" for issue in result["errors"])


def test_validate_mapping_requires_amount_for_direction_marker():
    result = validate_mapping(
        {
            "date": "วันที่",
            "description": "รายละเอียด",
            "direction_marker": "ประเภทรายการ",
        },
        ["วันที่", "รายละเอียด", "ประเภทรายการ"],
        bank="bay",
    )

    assert result["ok"] is False
    assert any(issue["code"] == "direction_marker_requires_amount" for issue in result["errors"])
