from utils.app_helpers import repair_suggested_mapping


def test_repair_suggested_mapping_protects_auto_debit_credit_from_stale_profile():
    columns = [
        "วันที่ทำรายการ",
        "เวลาที่ทำรายการ",
        "ประเภทรายการ",
        "ถอนเงิน",
        "ฝากเงิน",
        "ยอดเงินคงเหลือ",
        "IP Address",
    ]
    auto = {
        "date": "วันที่ทำรายการ",
        "description": "ประเภทรายการ",
        "time": "เวลาที่ทำรายการ",
        "debit": "ถอนเงิน",
        "credit": "ฝากเงิน",
        "amount": None,
        "balance": "ยอดเงินคงเหลือ",
    }
    stale_profile = {
        **auto,
        "description": "เวลาที่ทำรายการ",
        "time": "ประเภทรายการ",
        "debit": "IP Address",
    }

    repaired = repair_suggested_mapping(stale_profile, auto, columns)

    assert repaired["debit"] == "ถอนเงิน"
    assert repaired["credit"] == "ฝากเงิน"
    assert repaired["amount"] is None
    assert repaired["direction_marker"] is None
    assert repaired["description"] == "ประเภทรายการ"
    assert repaired["time"] == "เวลาที่ทำรายการ"
