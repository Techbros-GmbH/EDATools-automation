from __future__ import annotations

import pandas as pd

from .utils import _to_excel_bytes


class KQISummarizerBase:
    """Base class to keep a consistent interface."""

    source_name: str = "KQI"

    @staticmethod
    def to_excel_bytes(df: pd.DataFrame) -> bytes:
        return _to_excel_bytes(df)

    def summarize(self, df: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError
