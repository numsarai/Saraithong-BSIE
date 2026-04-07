from pathlib import Path

import pandas as pd

from core.subject_inference import infer_subject_identity


def test_infer_subject_identity_from_filename():
    result = infer_subject_identity(Path("ตัวอย่าง ไทยพาณิชย์ 68058421-6302541889 นาย กฤตกร เพิ่มพูล.xlsx"))

    assert result["account"] == "6302541889"
    assert result["name"] == "นาย กฤตกร เพิ่มพูล"


def test_infer_subject_identity_from_preview_when_filename_has_no_account():
    preview_df = pd.DataFrame([
        ["ชื่อบัญชี", "นาย ทดสอบ ระบบ", "", ""],
        ["เลขที่บัญชี", "123-456-7890", "", ""],
        ["วันที่", "รายการ", "จำนวนเงิน", "ยอดคงเหลือ"],
    ])

    result = infer_subject_identity(Path("stm วรุตม์.xlsx"), preview_df=preview_df)

    assert result["account"] == "1234567890"
    assert result["name"] == "นาย ทดสอบ ระบบ"
    assert result["account_source"] == "workbook_header"
    assert result["name_source"] == "workbook_header"


def test_infer_subject_identity_from_preview_handles_scientific_notation():
    preview_df = pd.DataFrame([
        ["เลขที่บัญชี", "1.23456789012E+11", "", ""],
        ["ชื่อบัญชี", "บริษัท ทดสอบ จำกัด", "", ""],
    ])

    result = infer_subject_identity(Path("stm.xlsx"), preview_df=preview_df)

    assert result["account"] == "123456789012"
    assert result["name"] == "บริษัท ทดสอบ จำกัด"


def test_infer_subject_identity_from_transaction_pattern():
    transaction_df = pd.DataFrame([
        {
            "บัญชีผู้โอน": "2109876543",
            "ชื่อผู้โอน": "สุดารัตน์ แสงทอง",
            "บัญชีผู้รับโอน": "3456789012",
            "ชื่อผู้รับโอน": "ประภาส พิชิต",
        },
        {
            "บัญชีผู้โอน": "0812345678",
            "ชื่อผู้โอน": "นภา จันทร์เพ็ญ",
            "บัญชีผู้รับโอน": "2109876543",
            "ชื่อผู้รับโอน": "สุดารัตน์ แสงทอง",
        },
        {
            "บัญชีผู้โอน": "2109876543",
            "ชื่อผู้โอน": "สุดารัตน์ แสงทอง",
            "บัญชีผู้รับโอน": "6667778889",
            "ชื่อผู้รับโอน": "อนันต์ เจริญผล",
        },
    ])

    result = infer_subject_identity(Path("sample_scb.xlsx"), preview_df=pd.DataFrame(), transaction_df=transaction_df)

    assert result["account"] == "2109876543"
    assert result["name"] == "สุดารัตน์ แสงทอง"
    assert result["account_source"] == "transaction_pattern"
    assert result["name_source"] == "transaction_pattern"


def test_infer_subject_identity_from_inline_header_text():
    preview_df = pd.DataFrame([
        ["รายการเดินบัญชีเงินฝากออมทรัพย์", "", "", ""],
        ["ของหมายเลขบัญชี 188-3-16739-9 ชื่อบัญชี นาย ศิระ ลิมปนันทพงศ์ สาขาโรบินสัน นครศรีธรรมราช", "", "", ""],
        ["ตั้งแต่วันที่ 01/01/2567 - 15/10/2568", "", "", ""],
        ["วันที่ทำรายการ", "เวลาที่ทำรายการ", "ประเภทรายการ", "ช่องทาง"],
    ])

    result = infer_subject_identity(Path("KBANK 1883167399 ใช้ทดสอบ.xlsx"), preview_df=preview_df)

    assert result["account"] == "1883167399"
    assert result["name"] == "นาย ศิระ ลิมปนันทพงศ์"
    assert result["account_source"] in {"filename", "workbook_header"}
    assert result["name_source"] == "workbook_header"
