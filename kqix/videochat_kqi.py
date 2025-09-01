from __future__ import annotations

import pandas as pd

from .base_kqi import KQISummarizerBase
from .utils import TECHNOLOGY_KEYWORDS

class VideoChatKQISummarizer(KQISummarizerBase):
    source_name = "VideoChat"

    def summarize(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()
        df.columns = df.columns.str.strip()
        if "Test Name" not in df.columns:
            return pd.DataFrame()

        vc = df[df["Test Name"] == "Data_VideoChat"].copy()
        if vc.empty:
            return pd.DataFrame()

        # column fallback map
        colmap = {
            "TWAMP_Latency_Score": ["TWAMP_Latency_Score", "Latency Score", "AR"],
            "TWAMP_Packet_Delay_Variation_Score": ["TWAMP Packet Delay Variation Score",
                                                   "TWAMP_Packet_Delay_Variation_Score", "AD"],
            "TWAMP_Packet_Loss_Score": ["TWAMP Packet Loss Score", "TWAMP_Packet_Loss_Score", "AU"],
            "TWAMP_Rtt_Min_ms": ["TWAMP_Rtt_Min_ms", "BL", "Rtt Min"],
            "TWAMP_Rtt_Average_ms": ["TWAMP_Rtt_Average_ms", "Rtt Average"],
            "TWAMP_Rtt_Median_ms": ["TWAMP_Rtt_Median_ms", "Rtt Median"],
            "TWAMP_Rtt_Max_ms": ["TWAMP_Rtt_Max_ms", "Rtt Max"],
            "TWAMP_Jitter_Min_ms": ["TWAMP_Jitter_Min_ms", "Jitter Min"],
            "TWAMP_Jitter_Average_ms": ["TWAMP_Jitter_Average_ms", "Jitter Average"],
            "TWAMP_Jitter_Median_ms": ["TWAMP_Jitter_Median_ms", "Jitter Median"],
            "TWAMP_Jitter_Max_ms": ["TWAMP_Jitter_Max_ms", "Jitter Max"],
        }
        actual = {}
        for std, alts in colmap.items():
            actual[std] = next((c for c in alts if c in vc.columns), None)

        if "Operator" not in vc.columns:
            vc["Operator"] = "Unknown"
        if "Type Mobility" not in vc.columns:
            vc["Type Mobility"] = "Unknown"
        if "Technology_Detail" not in vc.columns:
            vc["Technology_Detail"] = "Unknown"

        summary = []
        for (operator, test_name, mobility), group in vc.groupby(
            ["Operator", "Test Name", "Type Mobility"], dropna=False
        ):
            attempt = group["TWAMP Operation Attempt"].notna().sum() if "TWAMP Operation Attempt" in group.columns else 0
            success = group["TWAMP Operation Success"].notna().sum() if "TWAMP Operation Success" in group.columns else 0
            log_cnt = group["Logfile Name"].notna().sum() if "Logfile Name" in group.columns else 0
            status = "Success" if success >= log_cnt else "Failed"

            def smean(std_key):
                col = actual.get(std_key)
                s = pd.to_numeric(group[col], errors="coerce") if col else pd.Series(dtype=float)
                s = s.dropna()
                return round(s.mean(), 2) if not s.empty else "N/A"

            def smin(std_key):
                col = actual.get(std_key)
                s = pd.to_numeric(group[col], errors="coerce") if col else pd.Series(dtype=float)
                s = s.dropna()
                return round(s.min(), 2) if not s.empty else "N/A"

            def smed(std_key):
                col = actual.get(std_key)
                s = pd.to_numeric(group[col], errors="coerce") if col else pd.Series(dtype=float)
                s = s.dropna()
                return round(s.median(), 2) if not s.empty else "N/A"

            def smax(std_key):
                col = actual.get(std_key)
                s = pd.to_numeric(group[col], errors="coerce") if col else pd.Series(dtype=float)
                s = s.dropna()
                return round(s.max(), 2) if not s.empty else "N/A"

            row = {
                "Operator": operator,
                "Test Name": test_name,
                "Type Mobility": mobility,
                "Source": self.source_name,
                "TWAMP Operation Attempt": attempt,
                "TWAMP Operation Success": success,
                "Operation Status": status,
                "Qualified Session": success,  # fallback
                "Latency Score [Avg]": smean("TWAMP_Latency_Score"),
                "Packet Delay Variation Score [Avg]": smean("TWAMP_Packet_Delay_Variation_Score"),
                "Packet Loss Score [Avg]": smean("TWAMP_Packet_Loss_Score"),
                "Rtt Min (ms)": smin("TWAMP_Rtt_Min_ms"),
                "Rtt Average (ms)": smean("TWAMP_Rtt_Average_ms"),
                "Rtt Median (ms)": smed("TWAMP_Rtt_Median_ms"),
                "Rtt Max (ms)": smax("TWAMP_Rtt_Max_ms"),
                "Jitter Min (ms)": smin("TWAMP_Jitter_Min_ms"),
                "Jitter Average (ms)": smean("TWAMP_Jitter_Average_ms"),
                "Jitter Median (ms)": smed("TWAMP_Jitter_Median_ms"),
                "Jitter Max (ms)": smax("TWAMP_Jitter_Max_ms"),
            }

            total = len(group)
            for tech in TECHNOLOGY_KEYWORDS:
                cnt = group["Technology_Detail"].astype(str).str.contains(tech, na=False).sum()
                row[tech] = cnt
                row[f"{tech} (%)"] = round(cnt / total, 4) if total > 0 else 0.0

            summary.append(row)

        return pd.DataFrame(summary)