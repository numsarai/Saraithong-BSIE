from __future__ import annotations

import pandas as pd

from core.column_detector import detect_columns


def detect_mapping_for_dataframe(df: pd.DataFrame) -> dict:
    return detect_columns(df)
