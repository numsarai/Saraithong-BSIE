from __future__ import annotations

import pandas as pd

from core.bank_detector import detect_bank


def detect_bank_for_dataframe(df: pd.DataFrame, extra_text: str = "") -> dict:
    return detect_bank(df, extra_text=extra_text)
