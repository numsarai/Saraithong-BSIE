"""Regression tests for Thai/English column mapping into the English standard schema."""
import pandas as pd

from core.column_detector import detect_columns


def test_detect_columns_maps_mixed_thai_english_variants():
    """Common mixed-language statement headers should map into the English schema."""
    df = pd.DataFrame(columns=[
        "วัน-ที่ทำรายการ",
        "เวลา ทำรายการ",
        "Transaction Details / หมายเหตุ",
        "Debit Amount (THB)",
        "Credit Amount (THB)",
        "ยอดคงเหลือหลังรายการ",
        "ช่องทางบริการ",
        "Beneficiary Acc No.",
        "ชื่อผู้รับโอนเงิน",
    ])

    result = detect_columns(df)

    assert result["suggested_mapping"]["date"] == "วัน-ที่ทำรายการ"
    assert result["suggested_mapping"]["time"] == "เวลา ทำรายการ"
    assert result["suggested_mapping"]["description"] == "Transaction Details / หมายเหตุ"
    assert result["suggested_mapping"]["debit"] == "Debit Amount (THB)"
    assert result["suggested_mapping"]["credit"] == "Credit Amount (THB)"
    assert result["suggested_mapping"]["balance"] == "ยอดคงเหลือหลังรายการ"
    assert result["suggested_mapping"]["channel"] == "ช่องทางบริการ"
    assert result["suggested_mapping"]["counterparty_account"] == "Beneficiary Acc No."
    assert result["suggested_mapping"]["counterparty_name"] == "ชื่อผู้รับโอนเงิน"
    assert result["required_found"] is True


def test_detect_columns_uses_bank_template_sender_receiver_aliases_for_standard_fields():
    """Bank-template sender/receiver aliases should reinforce standard counterparty fields."""
    df = pd.DataFrame(columns=[
        "วันที่ทำรายการ",
        "รายละเอียด",
        "ถอนเงิน",
        "ฝากเงิน",
        "หมายเลขบัญชีปลายทาง",
        "ชื่อบัญชีปลายทาง",
    ])

    result = detect_columns(df)

    assert result["suggested_mapping"]["date"] == "วันที่ทำรายการ"
    assert result["suggested_mapping"]["description"] == "รายละเอียด"
    assert result["suggested_mapping"]["debit"] == "ถอนเงิน"
    assert result["suggested_mapping"]["credit"] == "ฝากเงิน"
    assert result["suggested_mapping"]["counterparty_account"] == "หมายเลขบัญชีปลายทาง"
    assert result["suggested_mapping"]["counterparty_name"] == "ชื่อบัญชีปลายทาง"
