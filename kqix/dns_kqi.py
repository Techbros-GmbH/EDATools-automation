from __future__ import annotations

import pandas as pd

from loguru import logger
from .base_kqi import KQISummarizerBase
from .utils import TECHNOLOGY_KEYWORDS


class DNSKQISummarizer(KQISummarizerBase):
    source_name = "DNS"

    def summarize(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()
        df.columns = df.columns.str.strip()

        # required columns
        for col in [
            "DNS Resolution Success Ratio (%)",
            "DNS_Host_Name_Resolution_Failure_Ratio",
            "DNS_Host_Name_Total_Resolution_Time_sec",
        ]:
            if col not in df.columns:
                logger.warning(f"Missing column for DNS: {col}")
                return pd.DataFrame()

        # keep Test Name
        if "Test Name" not in df.columns:
            if "Test_Name_2" in df.columns:
                df["Test Name"] = df["Test_Name_2"]
            else:
                df["Test Name"] = "DNS"

        if "Operator" not in df.columns:
            df["Operator"] = "Unknown"
        if "Type Mobility" not in df.columns:
            df["Type Mobility"] = "Unknown"
        if "Technology_Detail" not in df.columns:
            df["Technology_Detail"] = "Unknown"

        summary = []
        for (operator, test_name, mobility), group in df.groupby(
            ["Operator", "Test Name", "Type Mobility"], dropna=False
        ):
            total = len(group)
            success_ratio = pd.to_numeric(
                group["DNS Resolution Success Ratio (%)"], errors="coerce"
            ).mean()
            failure_ratio = pd.to_numeric(
                group["DNS_Host_Name_Resolution_Failure_Ratio"], errors="coerce"
            ).mean()

            res_time = pd.to_numeric(
                group["DNS_Host_Name_Total_Resolution_Time_sec"], errors="coerce"
            ).dropna()
            cnt_above_0_5 = (res_time > 0.5).sum()
            cnt_above_0_5_pct = round((cnt_above_0_5 / total) * 100, 2) if total > 0 else 0

            row = {
                "Operator": operator,
                "Test Name": test_name,
                "Type Mobility": mobility,
                "Source": self.source_name,
                "Total": total,
                "Attempt": total,
                "Success Ratio [%]": round(success_ratio, 2) if pd.notna(success_ratio) else 0,
                "DNS Host Name Resolution Failure Ratio": round(failure_ratio, 4) if pd.notna(failure_ratio) else 0,
                "Count > 0.5s [#]": cnt_above_0_5,
                "Count > 0.5s [%]": cnt_above_0_5_pct,
                "Min DNS Resolution Time (sec)": round(res_time.min(), 3) if not res_time.empty else None,
                "Average DNS Resolution Time (sec)": round(res_time.mean(), 3) if not res_time.empty else None,
                "Max DNS Resolution Time (sec)": round(res_time.max(), 3) if not res_time.empty else None,
            }

            for tech in TECHNOLOGY_KEYWORDS:
                cnt = group["Technology_Detail"].astype(str).str.contains(tech, na=False).sum()
                row[tech] = cnt
                row[f"{tech} (%)"] = round(cnt / total, 4) if total > 0 else 0.0

            summary.append(row)

        return pd.DataFrame(summary)