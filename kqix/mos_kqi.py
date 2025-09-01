from __future__ import annotations

import pandas as pd

from .base_kqi import KQISummarizerBase
from .utils import TECHNOLOGY_KEYWORDS

class MOSKQISummarizer(KQISummarizerBase):
    """Generic MOS summarizer. Set test_type to 'm2m' or 'ott' for label only."""
    source_name = "MOS"

    def __init__(self, test_type: str):
        self.test_type = test_type.lower()

    def summarize(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()
        df.columns = df.columns.str.strip()
        if "Operator" not in df.columns:
            df["Operator"] = "Unknown"
        if "Side" not in df.columns:
            df["Side"] = df.get("Test Side", "Unknown")
        if "Type Mobility" not in df.columns:
            df["Type Mobility"] = "Unknown"

        tech_col = "Technology_Detail"
        if tech_col not in df.columns:
            df[tech_col] = df.get("RadioAccessTechnologyState", "Unknown")

        if "Qualifier" not in df.columns:
            df["Qualifier"] = "Unknown"

        label = "M2M" if self.test_type == "m2m" else "OTT"
        summary = []

        for (operator, side), group in df.groupby(["Operator", "Side"], dropna=False):
            total = len(group)
            qualified = group["Qualifier"].astype(str).eq("Qualified").sum()

            mos_col = None
            if side in ("A", "Side A", "A "):
                mos_col = "POLQA SWB Score DL A"
            elif side in ("B", "Side B", "B "):
                mos_col = "POLQA SWB Score DL B"
            if mos_col not in group.columns:
                mos_col = "POLQA SWB Score DL" if "POLQA SWB Score DL" in group.columns else None

            mos_scores = pd.to_numeric(group.get(mos_col, pd.Series(dtype=float)), errors="coerce").dropna()

            poor_cnt = (mos_scores < 1.3).sum() if not mos_scores.empty else 0
            poor_ratio = round((poor_cnt / total) * 100, 1) if total > 0 else 0

            polqa_min = round(mos_scores.min(), 2) if not mos_scores.empty else None
            polqa_avg = round(mos_scores.mean(), 2) if not mos_scores.empty else None
            polqa_max = round(mos_scores.max(), 2) if not mos_scores.empty else None
            polqa_10 = round(mos_scores.quantile(0.10), 2) if not mos_scores.empty else None
            polqa_med = round(mos_scores.median(), 2) if not mos_scores.empty else None
            polqa_90 = round(mos_scores.quantile(0.90), 2) if not mos_scores.empty else None

            aqm_col = next((c for c in group.columns if "aqm" in c.lower() and "score" in c.lower()), None)
            aqm_scores = pd.to_numeric(group.get(aqm_col, pd.Series(dtype=float)), errors="coerce").dropna()
            aqm_min = round(aqm_scores.min(), 2) if not aqm_scores.empty else polqa_min
            aqm_avg = round(aqm_scores.mean(), 2) if not aqm_scores.empty else polqa_avg
            aqm_max = round(aqm_scores.max(), 2) if not aqm_scores.empty else polqa_max

            row = {
                "Operator": operator,
                "Operator Side": side,
                "Test Name": f"MOS {label}",
                "Type Mobility": group["Type Mobility"].iloc[0],
                "Source": self.source_name,
                "Samples Count": total,
                "Qualified Session": qualified,
                "MOS <= 1.3 COUNT": poor_cnt,
                "MOS <= 1.3 RATIO": f"{poor_ratio}%",
                "POLQA MIN MOS": polqa_min,
                "POLQA AVG MOS": polqa_avg,
                "POLQA MAX MOS": polqa_max,
                "POLQA 10 PCTL MOS": polqa_10,
                "POLQA Median MOS": polqa_med,
                "POLQA 90 PCTL MOS": polqa_90,
                "AQM Score MIN": aqm_min,
                "AQM Score AVG": aqm_avg,
                "AQM Score MAX": aqm_max,
            }

            for tech in TECHNOLOGY_KEYWORDS:
                cnt = group[tech_col].astype(str).str.contains(tech, na=False).sum()
                row[tech] = cnt
                row[f"{tech} (%)"] = round(cnt / total, 4) if total > 0 else 0.0

            summary.append(row)

        return pd.DataFrame(summary)