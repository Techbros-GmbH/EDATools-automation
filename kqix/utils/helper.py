from __future__ import annotations

from io import BytesIO

import pandas as pd

TECHNOLOGY_KEYWORDS = [
    "GSM",
    "UMTS",
    "LTE",
    "EN-DC",
    "NR",
    "NR/UMTS",
    "GSM/NR",
    "NR/LTE",
    "NR/EN-DC",
    "LTE/EN-DC",
    "GSM/UMTS",
    "UMTS/LTE",
    "NR/LTE/EN-DC",
    "UMTS/NR/EN-DC",
    "UMTS/LTE/NR",
    "GSM/NR/EN-DC",
    "GSM/LTE/NR",
    "GSM/UMTS/NR",
    "UMTS/LTE/EN-DC",
    "GSM/LTE",
    "GSM/LTE/EN-DC",
    "GSM/UMTS/LTE",
    "NR/UMTS/LTE/EN-DC",
    "GSM/NR/LTE/EN-DC",
    "GSM/UMTS/NR/EN-DC",
    "GSM/UMTS/LTE/NR",
    "GSM/UMTS/LTE/EN-DC",
    "GSM/UMTS/LTE/EN-DC/NR",
]


def _to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    return buf.getvalue()


def _pct(n: float) -> str:
    return f"{n * 100:.1f}%" if isinstance(n, (int, float)) else "Null"
