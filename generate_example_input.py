"""
generate_example_input.py
-------------------------
Creates a realistic example bank statement Excel file for SCB-format testing.
Run this script once to generate: data/input/example_scb.xlsx

Includes edge cases:
- Thai text descriptions
- Mixed Thai/English descriptions
- Counterparty accounts (valid and partial)
- Scientific notation account (will be parsed safely)
- Missing counterparty fields
- Deposits, withdrawals, transfers
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd


def generate_scb_example():
    """Generate a realistic SCB-format bank statement."""
    data = {
        "วันที่": [
            "01/01/2024", "02/01/2024", "03/01/2024", "04/01/2024",
            "05/01/2024", "06/01/2024", "07/01/2024", "08/01/2024",
            "09/01/2024", "10/01/2024", "11/01/2024", "12/01/2024",
            "13/01/2024", "14/01/2024",
        ],
        "เวลา": [
            "09:15:33", "11:22:10", "13:45:00", "08:00:00",
            "14:30:55", "09:00:00", "16:20:11", "10:05:30",
            "12:00:00", "15:45:22", "08:30:00", "17:00:00",
            "11:11:11", "14:59:59",
        ],
        "รายการ": [
            "ฝากเงิน CDM",                                   # DEPOSIT - Thai
            "โอนเงิน PromptPay จาก 0812345678",             # TRANSFER - Thai
            "ATM ถอนเงิน สาขา CentralWorld",                # WITHDRAW - Thai
            "โอนเงิน SCB EASY บัญชี 1234567890",            # TRANSFER with account
            "Cash Deposit via ATM",                          # DEPOSIT - English
            "Transfer from Savings 9876543210",              # TRANSFER - English account
            "ถอนเงิน ATM พัทยา",                            # WITHDRAW - Thai
            "ฝากเงินสด Counter",                             # DEPOSIT - Thai
            "InterBank Transfer KBANK",                      # TRANSFER - English
            "PromptPay OUT to 0987654321",                   # TRANSFER-keyword
            "ค่าน้ำค่าไฟ บริษัท ABC",                       # UNKNOWN OUT
            "รับเงินโอน บริษัท XYZ จำกัด",                 # TRANSFER IN
            "SCB Easy Pay",                                  # UNKNOWN
            "Cash Withdrawal",                               # WITHDRAW - English
        ],
        "จำนวนเงิน": [
            "5000.00", "-2000.00", "-1500.00", "-3000.00",
            "10000.00", "25000.00", "-500.00", "1000.00",
            "50000.00", "-8000.00", "-1200.00", "7500.00",
            "-300.00", "-2500.00",
        ],
        "ยอดคงเหลือ": [
            "15000.00", "13000.00", "11500.00", "8500.00",
            "18500.00", "43500.00", "43000.00", "44000.00",
            "94000.00", "86000.00", "84800.00", "92300.00",
            "92000.00", "89500.00",
        ],
        "ช่องทาง": [
            "CDM", "Mobile Banking", "ATM", "Mobile Banking",
            "ATM", "Mobile Banking", "ATM", "Counter",
            "Mobile Banking", "Mobile Banking", "Mobile Banking", "Mobile Banking",
            "Mobile Banking", "ATM",
        ],
        "บัญชีคู่โอน": [
            "",               # No counterparty (deposit)
            "0812345678",     # Partial (phone-format → partial account)
            "",               # ATM withdraw
            "1234567890",     # Valid 10-digit account
            "",               # CDM deposit
            "9876543210",     # Valid 10-digit account
            "",               # ATM
            "",               # Counter
            "123456789012",   # Valid 12-digit account
            "0987654321",     # Partial (10-digit phone, will be validated)
            "",               # Unknown
            "112233445566",   # Valid 12-digit account
            "",               # Unknown
            "",               # ATM
        ],
        "ชื่อคู่โอน": [
            "",
            "นายสมชาย ใจดี",
            "",
            "บริษัท เอบีซี จำกัด",
            "",
            "นางสาวมาลี สวย",
            "",
            "",
            "ห้างหุ้นส่วน เดลต้า",
            "นายธนากร รวย",
            "",
            "บริษัท XYZ จำกัด",
            "",
            "",
        ],
    }

    df = pd.DataFrame(data)
    out_path = Path(__file__).parent / "data" / "input" / "example_scb.xlsx"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(out_path, index=False)
    print(f"✅ Generated: {out_path}")
    return out_path


if __name__ == "__main__":
    generate_scb_example()
