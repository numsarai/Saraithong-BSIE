from pathlib import Path

import pandas as pd

from core.ofx_io import export_ofx, infer_identity_from_ofx, parse_ofx_file


def test_parse_ofx_file_reads_bank_account_transactions(tmp_path):
    ofx_path = tmp_path / "sample.ofx"
    ofx_path.write_text(
        """OFXHEADER:100
DATA:OFXSGML
VERSION:102

<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<BANKACCTFROM>
<ACCTID>1234567890
</BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260301091500
<TRNAMT>100.00
<FITID>F1
<NAME>Alice
<MEMO>Transfer in
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260302093000
<TRNAMT>-50.00
<FITID>F2
<NAME>Bob
<MEMO>Transfer out
</STMTTRN>
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
""",
        encoding="utf-8",
    )

    df = parse_ofx_file(ofx_path)
    assert len(df) == 2
    assert df.iloc[0]["subject_account"] == "1234567890"
    assert df.iloc[0]["direction"] == "IN"
    assert df.iloc[1]["direction"] == "OUT"
    assert infer_identity_from_ofx(ofx_path, df)["account"] == "1234567890"


def test_export_ofx_writes_statement_blocks():
    transactions = pd.DataFrame([
        {
            "transaction_id": "TXN-1",
            "date": "2026-03-01",
            "time": "09:15:00",
            "amount": 100.0,
            "balance": 100.0,
            "counterparty_name": "Alice",
            "description": "Transfer in",
        }
    ])

    rendered = export_ofx(transactions, account_number="1234567890", bank="SCB", subject_name="Subject")
    assert "<ACCTID>1234567890" in rendered
    assert "<TRNAMT>100.00" in rendered
    assert "<FITID>TXN-1" in rendered
