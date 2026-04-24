import pandas as pd

from core.normalizer import normalize


def test_normalize_direction_marker_format_signs_unsigned_amounts():
    df = pd.DataFrame(
        [
            {"วันที่": "2026-01-08", "รายละเอียด": "โอนเงินไป 1234500001", "ประเภทรายการ": "DR", "จำนวนเงิน": "500.00", "ยอดคงเหลือ": "20,500.00"},
            {"วันที่": "2026-01-09", "รายละเอียด": "รับโอนจาก 1234500002", "ประเภทรายการ": "CR", "จำนวนเงิน": "1,600.00", "ยอดคงเหลือ": "22,100.00"},
        ]
    )
    cfg = {
        "bank_name": "BAY",
        "format_type": "direction_marker",
        "amount_mode": "direction_marker",
        "currency": "THB",
        "column_mapping": {
            "date": ["วันที่"],
            "description": ["รายละเอียด"],
            "direction_marker": ["ประเภทรายการ"],
            "amount": ["จำนวนเงิน"],
            "balance": ["ยอดคงเหลือ"],
        },
    }

    result = normalize(df, cfg, subject_account="6941230651", subject_name="Subject")

    assert list(result["amount"]) == [-500.0, 1600.0]
    assert list(result["direction"]) == ["OUT", "IN"]
    assert list(result["counterparty_account"]) == ["1234500001", "1234500002"]
