from __future__ import annotations

import pandas as pd

from core.normalizer import normalize


def normalize_dataframe(df: pd.DataFrame, bank_config: dict, subject_account: str, subject_name: str = "", source_file: str = "") -> pd.DataFrame:
    return normalize(df, bank_config, subject_account, subject_name=subject_name, source_file=source_file)
