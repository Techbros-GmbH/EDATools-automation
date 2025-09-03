from __future__ import annotations

import pandas as pd

from .base_kqi import KQISummarizerBase
from .utils import TECHNOLOGY_KEYWORDS

class StreamingKQISummarizer(KQISummarizerBase):
    source_name = "Streaming"

    def summarize(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df.columns = df.columns.str.strip()
        summary = []

        for (operator, test_name, mobility), group in df.groupby(
            ["Operator", "Test Name", "Session Start Technology"], dropna=False
        ):
            total = len(group)
            success = group["Streaming Success Rate"].astype(str).eq("100").sum()
            failures = total - success
            success_ratio = round((success / total) * 100, 2) if total > 0 else 0

            row = {
                "Operator": operator,
                "Test Name": test_name,
                "Type Mobility": mobility,
                "Source": self.source_name,
                "Total": total,
                "Attempt": total,
                "Success": success,
                "Failures": failures,
                "Success Ratio [%]": success_ratio,
            }

            for tech in TECHNOLOGY_KEYWORDS:
                cnt = group["Session Start Technology"].astype(str).str.contains(tech, na=False).sum()
                row[tech] = cnt
                row[f"{tech} (%)"] = round(cnt / total, 4) if total > 0 else 0.0

            summary.append(row)

        return pd.DataFrame(summary)
