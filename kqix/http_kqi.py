from __future__ import annotations

import pandas as pd

from .base_kqi import KQISummarizerBase
from .utils import TECHNOLOGY_KEYWORDS

class HttpKQISummarizer(KQISummarizerBase):
    source_name = "HTTP"

    def summarize(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df.columns = df.columns.str.strip()

        throughput_col = "HttpMeanDataRate"
        ulthroughput_col = "HTTP_Upload_Average_Throughput"
        status_col = "HttpServiceStatus"
        mobility_col = "Type Mobility"
        tech_col = "Technology_Detail"
        test_col = "Test Name"
        browsing_col = "HttpDataTransferTime"
        setup_time_col = "HttpIpServiceSetupTime"

        summary = []
        for (operator, test_name, mobility), group in df.groupby(
            ["Operator", test_col, mobility_col], dropna=False
        ):
            total = len(group)
            success = group[status_col].astype(str).eq("Succeeded").sum()
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
                cnt = group[tech_col].astype(str).str.contains(tech, na=False).sum()
                row[tech] = cnt
                row[f"{tech} (%)"] = round(cnt / total, 4) if total > 0 else 0.0

            if test_name in ["HTTP FDFS DL", "HTTP FDTT DL", "HTTP FDTT UL"]:
                thp = (
                    pd.to_numeric(group[throughput_col], errors="coerce").dropna()
                    / 1000
                )
                row["Average"] = round(thp.mean(), 2) if not thp.empty else None
                row["Median"] = round(thp.median(), 2) if not thp.empty else None
                row["P95"] = round(thp.quantile(0.95), 2) if not thp.empty else None
                row["Max"] = round(thp.max(), 2) if not thp.empty else None

                if test_name == "HTTP FDFS DL":
                    row["Count > 1 Mbps"] = (thp > 1).sum()
                    row["Count > 3 Mbps"] = (thp > 3).sum()
                elif test_name == "HTTP FDTT DL":
                    row["Count > 100 Mbps"] = (thp > 100).sum()
                    row["Count > 20 Mbps"] = (thp > 20).sum()
                elif test_name == "HTTP FDTT UL":
                    row["Count > 5 Mbps"] = (thp > 5).sum()
                    row["Count > 2 Mbps"] = (thp > 2).sum()

            elif test_name in ["HTTP FDFS UL"]:
                thp = (
                    pd.to_numeric(group[ulthroughput_col], errors="coerce").dropna()
                    / 1000
                )
                row["Average"] = round(thp.mean(), 2) if not thp.empty else None
                row["Median"] = round(thp.median(), 2) if not thp.empty else None
                row["P95"] = round(thp.quantile(0.95), 2) if not thp.empty else None
                row["Max"] = round(thp.max(), 2) if not thp.empty else None
                row["Count > 1 Mbps"] = (thp > 1).sum()

            elif test_name in ["HTTP BROWSING LIVE", "HTTP BROSWING STATIC"]:
                setup = pd.to_numeric(group[setup_time_col], errors="coerce").dropna()
                row["Average"] = round(setup.mean(), 2) if not setup.empty else None
                row["Median"] = round(setup.median(), 2) if not setup.empty else None
                row["P95"] = round(setup.quantile(0.95), 2) if not setup.empty else None
                row["Max"] = round(setup.max(), 2) if not setup.empty else None

                dtt = pd.to_numeric(group[browsing_col], errors="coerce").dropna()
                row["Avg Data Rate"] = round(dtt.mean(), 2) if not dtt.empty else None

            summary.append(row)

        return pd.DataFrame(summary)
