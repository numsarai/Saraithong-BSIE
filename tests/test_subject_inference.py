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
