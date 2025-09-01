from __future__ import annotations

import pandas as pd
import numpy as np


from .base_kqi import KQISummarizerBase
from .utils import TECHNOLOGY_KEYWORDS, _pct

class VoiceKQISummarizer(KQISummarizerBase):
    """Use test_type='m2m' or 'ott' to label."""
    source_name = "Voice"

    def __init__(self, test_type: str):
        self.test_type = test_type.lower()

    def summarize(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()
        df.columns = df.columns.str.strip()
        label = "M2M" if self.test_type == "m2m" else "OTT"
        summary = []

        for (operator, side), group in df.groupby(["Operator", "Side"], dropna=False):
            def pick(*names):
                for n in names:
                    if n in group.columns:
                        return n
                return None

            call_attempt_col = pick(f"Call Attempt {side}", "Call Attempt")
            qualifier_col = pick(f"Qualifier {side}", "Qualifier")
            setup_succ_rate_col = pick(f"Call Setup Success Rate {side}", "Voice_Call_Setup_Success_Rate")
            completion_rate_col = pick(f"Call Completion Rate {side}", "Voice_Call_Completion_Rate")
            success_rate_col = pick(f"Call Success Rate {side}", "Voice_Call_Success_Rate")
            drop_rate_col = pick(f"Call Drop Rate {side}", "Voice_Dropped_Call_Rate")
            block_rate_col = pick(f"Call Block Rate {side}", "Call Block Rate")
            setup_fail_rate_col = pick(f"Call Setup Failure Rate {side}", "Voice_Call_Setup_Failure_Rate")
            call_dur_col = pick(f"Call Duration {side}", "Call_Duration")
            setup_time_col = pick(f"Call Setup Time (sec) {side}", "Call_Setup_Time_sec")
            multi_rab_col = pick(f"Is_Multi_RAB {side}", "Is_Multi_RAB")
            sq_mos_col = pick(f"SQ MOS {side}", "SQ_MOS")
            polqa_col = pick(f"POLQA SWB Score DL {side}", "POLQA SWB Score DL")

            def s(col):
                return group[col] if col and col in group.columns else pd.Series(dtype="float")

            call_attempts = s(call_attempt_col).astype(str).eq("Call Attempt").sum()
            qualified = s(qualifier_col).astype(str).eq("Qualified").sum()

            def mean_pct(col):
                ser = pd.to_numeric(s(col), errors="coerce")
                return (ser/100).mean() if not ser.empty and not ser.isna().all() else "Null"

            setup_succ_rate = mean_pct(setup_succ_rate_col)
            completed_calls = s(completion_rate_col).astype(float).eq(100).sum()
            completion_rate = mean_pct(completion_rate_col)
            success_rate = mean_pct(success_rate_col)

            dropped_calls = s(drop_rate_col).astype(float).eq(100).sum()
            dropped_ratio = mean_pct(drop_rate_col)
            blocked_calls = s(block_rate_col).astype(float).eq(100).sum()
            blocked_ratio = mean_pct(block_rate_col)
            setup_fail_rate = mean_pct(setup_fail_rate_col)
            overall_failed = call_attempts - completed_calls

            durations = pd.to_numeric(s(call_dur_col), errors="coerce").dropna()
            min_duration = round(durations.min(), 2) if not durations.empty else "Null"
            avg_duration = round(durations.mean(), 2) if not durations.empty else "Null"
            max_duration = round(durations.max(), 2) if not durations.empty else "Null"

            setup_times = pd.to_numeric(s(setup_time_col), errors="coerce").dropna()
            min_setup = round(setup_times.min(), 2) if not setup_times.empty else "Null"
            avg_setup = round(setup_times.mean(), 2) if not setup_times.empty else "Null"
            max_setup = round(setup_times.max(), 2) if not setup_times.empty else "Null"
            p10 = round(np.percentile(setup_times, 10), 2) if len(setup_times) else "Null"
            p50 = round(np.percentile(setup_times, 50), 2) if len(setup_times) else "Null"
            p90 = round(np.percentile(setup_times, 90), 2) if len(setup_times) else "Null"
            gt4 = int((setup_times > 4).sum())
            le4 = int((setup_times <= 4).sum())

            polqa = pd.to_numeric(s(polqa_col), errors="coerce").dropna()
            polqa_min = round(polqa.min(), 2) if len(polqa) else "Null"
            polqa_avg = round(polqa.mean(), 2) if len(polqa) else "Null"
            polqa_max = round(polqa.max(), 2) if len(polqa) else "Null"
            polqa_10 = round(np.percentile(polqa, 10), 2) if len(polqa) else "Null"
            polqa_med = round(np.percentile(polqa, 50), 2) if len(polqa) else "Null"
            polqa_90 = round(np.percentile(polqa, 90), 2) if len(polqa) else "Null"

            sq = pd.to_numeric(s(sq_mos_col), errors="coerce")
            sample_count = int(sq.count())
            poor_count = int((sq <= 1.3).sum()) if sample_count else 0
            poor_ratio = round((poor_count / sample_count) * 100, 1) if sample_count else 0

            aqm = pd.to_numeric(s("AQM Score" if f"AQM Score {side}" not in group.columns else f"AQM Score {side}"),
                                errors="coerce").dropna()
            aqm_min = round(aqm.min(), 2) if len(aqm) else "Null"
            aqm_avg = round(aqm.mean(), 2) if len(aqm) else "Null"
            aqm_max = round(aqm.max(), 2) if len(aqm) else "Null"

            mrab_series = s(multi_rab_col).astype(str)
            multirab_status = "True" if mrab_series.str.contains("True", case=False, na=False).any() else "False"
            multirab_success = int(mrab_series.str.contains("True", case=False, na=False).sum())
            multirab_ratio = multirab_success / len(mrab_series) if len(mrab_series) else 0

            row = {
                "Operator": operator,
                "Operator Side": side,
                "Test Name": f"Voice {label}",
                "Type Mobility": group["Type Mobility"].iloc[0] if "Type Mobility" in group.columns else "Unknown",
                "Source": self.source_name,
                "Samples Count": sample_count,
                "Call Attempts": call_attempts,
                "Qualified Session": qualified,
                "Call Setup Success Count": int(pd.to_numeric(s(setup_succ_rate_col), errors="coerce").eq(100).sum())
                    if setup_succ_rate_col else 0,
                "Voice Call setup success rate (%)": _pct(setup_succ_rate) if setup_succ_rate != "Null" else "Null",
                "Completed Calls Count": completed_calls,
                "Voice Call completion rate (%)": _pct(completion_rate) if completion_rate != "Null" else "Null",
                "Voice Call success rate (%)": _pct(success_rate) if success_rate != "Null" else "Null",
                "Dropped Calls Count": dropped_calls,
                "Dropped Calls Ratio": _pct(dropped_ratio) if dropped_ratio != "Null" else "Null",
                "Blocked Calls Count": blocked_calls,
                "Blocked Calls Ratio": _pct(blocked_ratio) if blocked_ratio != "Null" else "Null",
                "Overall Failed": overall_failed,
                "Voice Call setup failure rate (%)": _pct(setup_fail_rate) if setup_fail_rate != "Null" else "Null",
                "MIN Call duration (s)": min_duration,
                "Avg Call duration (s)": avg_duration,
                "MAX Call duration (s)": max_duration,
                "MIN Call Setup time sec": min_setup,
                "Avg Call Setup time sec": avg_setup,
                "MAX Call Setup Time sec": max_setup,
                "10 PCTL Call setup time sec": p10,
                "Median Call setup time sec": p50,
                "90 PCTL Call setup time sec": p90,
                "Call Setup Time > 4 s count": gt4,
                "Call Setup Time <= 4 s count": le4,
                "MultiRAB Status": multirab_status,
                "MultiRAB Success Count": multirab_success,
                "MultiRAB Ratio": _pct(multirab_ratio),
                "POLQA MIN MOS": polqa_min,
                "POLQA AVG MOS": polqa_avg,
                "POLQA MAX MOS": polqa_max,
                "POLQA 10 PCTL MOS": polqa_10,
                "POLQA Median MOS": polqa_med,
                "POLQA 90 PCTL MOS": polqa_90,
                "MOS <= 1.3 COUNT": poor_count,
                "MOS <= 1.3 RATIO": poor_ratio,
                "AQM Score MIN": aqm_min,
                "AQM Score AVG": aqm_avg,
                "AQM Score MAX": aqm_max,
            }

            # optional tech split if present
            if "Technology_Detail" in group.columns:
                total_samples = len(group)
                for tech in TECHNOLOGY_KEYWORDS:
                    cnt = group["Technology_Detail"].astype(str).str.contains(tech, na=False, case=False).sum()
                    row[tech] = cnt
                    row[f"{tech} (%)"] = round((cnt / total_samples), 4) if total_samples else 0.0

            summary.append(row)

        return pd.DataFrame(summary)