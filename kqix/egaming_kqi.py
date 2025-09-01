from __future__ import annotations

import pandas as pd

from .base_kqi import KQISummarizerBase
from .utils import TECHNOLOGY_KEYWORDS

class EgamingKQISummarizer(KQISummarizerBase):
    source_name = "eGaming"

    def summarize(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df.columns = df.columns.str.strip()
        summary = []

        for (operator, test_name, mobility), group in df.groupby(
            ["Operator", "Test Name", "Type Mobility"], dropna=False
        ):
            attempt = group["TWAMP Operation Attempt"].count()
            success = group["TWAMP Operation Success"].count()
            status = "Success" if success > attempt else "Failed"

            latency = pd.to_numeric(group.get("TWAMP_Latency_Score"), errors="coerce").mean()
            pdelay = pd.to_numeric(group.get("TWAMP_Packet_Delay_Variation_Score"), errors="coerce").mean()
            loss = pd.to_numeric(group.get("TWAMP_Packet_Loss_Score"), errors="coerce").mean()

            rttmin = pd.to_numeric(group.get("TWAMP_Rtt_Min_ms"), errors="coerce").min()
            rttavg = pd.to_numeric(group.get("TWAMP_Rtt_Average_ms"), errors="coerce").mean()
            rttmed = pd.to_numeric(group.get("TWAMP_Rtt_Median_ms"), errors="coerce").median()
            rttmax = pd.to_numeric(group.get("TWAMP_Rtt_Max_ms"), errors="coerce").max()

            jitmin = pd.to_numeric(group.get("TWAMP_Jitter_Min_ms"), errors="coerce").min()
            jitavg = pd.to_numeric(group.get("TWAMP_Jitter_Average_ms"), errors="coerce").mean()
            jitmed = pd.to_numeric(group.get("TWAMP_Jitter_Median_ms"), errors="coerce").median()
            jitmax = pd.to_numeric(group.get("TWAMP_Jitter_Max_ms"), errors="coerce").max()

            total = len(group)
            row = {
                "Operator": operator,
                "Test Name": test_name,
                "Type Mobility": mobility,
                "Source": self.source_name,
                "TWAMP Operation Attempt": attempt,
                "TWAMP Operation Success": success,
                "Operation Status": status,
                "Latency Score [Avg]": round(latency, 2) if pd.notna(latency) else None,
                "Packet Delay Variation Score [Avg]": round(pdelay, 2) if pd.notna(pdelay) else None,
                "Packet Loss Score [Avg]": round(loss, 2) if pd.notna(loss) else None,
                "Rtt Min (ms)": round(rttmin, 2) if pd.notna(rttmin) else None,
                "Rtt Average (ms)": round(rttavg, 2) if pd.notna(rttavg) else None,
                "Rtt Median (ms)": round(rttmed, 2) if pd.notna(rttmed) else None,
                "Rtt Max (ms)": round(rttmax, 2) if pd.notna(rttmax) else None,
                "Jitter Min (ms)": round(jitmin, 2) if pd.notna(jitmin) else None,
                "Jitter Average (ms)": round(jitavg, 2) if pd.notna(jitavg) else None,
                "Jitter Median (ms)": round(jitmed, 2) if pd.notna(jitmed) else None,
                "Jitter Max (ms)": round(jitmax, 2) if pd.notna(jitmax) else None,
            }

            for tech in TECHNOLOGY_KEYWORDS:
                cnt = group["Technology_Detail"].astype(str).str.contains(tech, na=False).sum()
                row[tech] = cnt
                row[f"{tech} (%)"] = round(cnt / total, 4) if total > 0 else 0.0

            summary.append(row)

        return pd.DataFrame(summary)
