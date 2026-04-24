from utils.app_helpers import repair_suggested_mapping


def test_repair_suggested_mapping_prefers_curated_balance_alias():
    repaired = repair_suggested_mapping(
        {
            "date": "วันที่",
            "description": "คำอธิบายรายการ",
            "amount": "ยอดเงิน",
            "balance": "ยอดหลังรายการ",
        },
        {},
        ["วันที่", "คำอธิบายรายการ", "ยอดเงิน", "ยอดคงเหลือ", "ยอดหลังรายการ"],
    )

    assert repaired["balance"] == "ยอดคงเหลือ"


def test_repair_suggested_mapping_keeps_after_transaction_balance_when_no_better_alias():
    repaired = repair_suggested_mapping(
        {
            "date": "วันที่",
            "description": "คำอธิบายรายการ",
            "amount": "ยอดเงิน",
            "balance": "ยอดหลังรายการ",
        },
        {},
        ["วันที่", "คำอธิบายรายการ", "ยอดเงิน", "ยอดหลังรายการ"],
    )

    assert repaired["balance"] == "ยอดหลังรายการ"
