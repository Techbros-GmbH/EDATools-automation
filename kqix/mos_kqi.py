from __future__ import annotations

import re
import pandas as pd
from loguru import logger
from .base_kqi import KQISummarizerBase
from .utils import TECHNOLOGY_KEYWORDS


class MOSKQISummarizer(KQISummarizerBase):
    """Generic MOS summarizer. Set test_type to 'm2m' or 'ott' for label only."""
    source_name = "MOS"

    def __init__(self, test_type: str):
        self.test_type = test_type.lower()
        logger.debug(f"test_type: {test_type}")

    @staticmethod
    def _wide_to_long(df: pd.DataFrame) -> pd.DataFrame:
        """Convert A/B-suffixed wide MOS sheet to long format with 'Side' column
        and unified fields:
          - 'Type Mobility'         <- Type Mobility A/B
          - 'Technology_Detail'     <- Technology Detail A/B (or RAT fallbacks)
          - 'POLQA SWB Score DL'    <- POLQA SWB Score DL A/B
          - 'Qualifier'             <- Qualifier (SQ MOS A/B)
        """
        df = df.copy()
        df.columns = df.columns.str.strip()

        # columns shared by both sides = not ending with ' A' or ' B'
        shared = [c for c in df.columns if not re.search(r"\s[AB]$", c)]

        # detect base names that have A/B pairs
        bases = set()
        for c in df.columns:
            m = re.match(r"^(.*)\s([AB])$", c)
            if m:
                bases.add(m.group(1).strip())

        parts = []
        for side in ("A", "B"):
            side_map = {f"{b} {side}": b for b in bases if f"{b} {side}" in df.columns}
            if not side_map:
                continue

            view = pd.concat([df[shared].copy(), df[list(side_map.keys())].copy()], axis=1)
            view.rename(columns=side_map, inplace=True)  # "... A/B" -> base

            # Side label
            view["Side"] = f"Side {side}"

            # Qualifier
            qcol = f"Qualifier (SQ MOS {side})"
            if qcol in view.columns:
                view["Qualifier"] = view[qcol]
            elif "Qualifier" not in view.columns:
                view["Qualifier"] = "Unknown"

            # Type Mobility (take side-specific if present)
            tm_side = f"Type Mobility {side}"
            if tm_side in df.columns:
                view["Type Mobility"] = df[tm_side].values
            else:
                view.setdefault("Type Mobility", "Unknown")

            # Technology detail
            if "Technology Detail" in view.columns:
                view["Technology_Detail"] = view["Technology Detail"]
            else:
                td_side = f"Technology Detail {side}"
                if td_side in df.columns:
                    view["Technology_Detail"] = df[td_side].values
                else:
                    # try RAT columns as fallback (some sheets repeat this name)
                    rat_like = [c for c in view.columns if "Radio Access Technology" in c]
                    if rat_like:
                        view["Technology_Detail"] = view[rat_like[0]]
                    else:
                        view["Technology_Detail"] = "Unknown"

            # Unified POLQA column
            if "POLQA SWB Score DL" in view.columns:
                view["POLQA SWB Score DL"] = pd.to_numeric(view["POLQA SWB Score DL"], errors="coerce")
            else:
                polqa_side = f"POLQA SWB Score DL {side}"
                if polqa_side in df.columns:
                    view["POLQA SWB Score DL"] = pd.to_numeric(df[polqa_side], errors="coerce")
                else:
                    view["POLQA SWB Score DL"] = pd.Series(dtype=float)

            parts.append(view)

        if not parts:
            # fallback: no A/B pairs detected → at least produce a single side
            df["Side"] = "Unknown"
            if "Qualifier" not in df.columns:
                if "Qualifier (SQ MOS A)" in df.columns:
                    df["Qualifier"] = df["Qualifier (SQ MOS A)"]
                elif "Qualifier (SQ MOS B)" in df.columns:
                    df["Qualifier"] = df["Qualifier (SQ MOS B)"]
                else:
                    df["Qualifier"] = "Unknown"
            if "Type Mobility" not in df.columns:
                df["Type Mobility"] = df.get("Type Mobility A", df.get("Type Mobility B", "Unknown"))
            if "Technology_Detail" not in df.columns:
                df["Technology_Detail"] = df.get(
                    "Technology Detail A",
                    df.get("Technology Detail B", "Unknown"),
                )
            return df

        out = pd.concat(parts, ignore_index=True)
        # drop accidental duplicate column names after concat
        out = out.loc[:, ~out.columns.duplicated()]
        return out

    def summarize(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()
        df.columns = df.columns.str.strip()

        # Ensure global fields exist
        if "Operator" not in df.columns:
            df["Operator"] = "Unknown"

        # Convert wide A/B to long with proper 'Side'
        df = self._wide_to_long(df)

        # Final safety nets
        for must in ("Operator", "Side", "Type Mobility", "Qualifier", "Technology_Detail"):
            if must not in df.columns:
                df[must] = "Unknown"

        label = "M2M" if self.test_type == "m2m" else "OTT"
        summary = []

        for (operator, side), group in df.groupby(["Operator", "Side"], dropna=False):
            total = int(len(group))
            if total == 0:
                continue

            qualified = int(group["Qualifier"].astype(str).str.strip().eq("Qualified").sum())

            # Prefer unified POLQA
            if "POLQA SWB Score DL" in group.columns:
                mos_col = "POLQA SWB Score DL"
            elif side in ("Side A", "A"):
                mos_col = "POLQA SWB Score DL A" if "POLQA SWB Score DL A" in group.columns else None
            elif side in ("Side B", "B"):
                mos_col = "POLQA SWB Score DL B" if "POLQA SWB Score DL B" in group.columns else None
            else:
                mos_col = None

            mos_scores = pd.to_numeric(group.get(mos_col, pd.Series(dtype=float)), errors="coerce").dropna()

            poor_cnt = int((mos_scores < 1.3).sum()) if not mos_scores.empty else 0
            poor_ratio = round((poor_cnt / total) * 100, 1) if total > 0 else 0.0

            polqa_min = round(mos_scores.min(), 2) if not mos_scores.empty else None
            polqa_avg = round(mos_scores.mean(), 2) if not mos_scores.empty else None
            polqa_max = round(mos_scores.max(), 2) if not mos_scores.empty else None
            polqa_10  = round(mos_scores.quantile(0.10), 2) if not mos_scores.empty else None
            polqa_med = round(mos_scores.median(), 2) if not mos_scores.empty else None
            polqa_90  = round(mos_scores.quantile(0.90), 2) if not mos_scores.empty else None

            # AQM: pick any score-like AQM column available
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

            # Technology breakdown counts (case-insensitive)
            tech_col = "Technology_Detail"
            for tech in TECHNOLOGY_KEYWORDS:
                cnt = int(group[tech_col].astype(str).str.contains(tech, case=False, na=False).sum())
                row[tech] = cnt
                row[f"{tech} (%)"] = round(cnt / total, 4) if total > 0 else 0.0

            summary.append(row)

        return pd.DataFrame(summary)
