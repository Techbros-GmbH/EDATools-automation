import re
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import Any, List, Tuple

import pandas as pd
from loguru import logger
from .parsing_config import (
    MOS_OTT_AGG_RULES,
    MOS_OTT_COLUMNS_AFTER_FFILL,
    MOS_OTT_COLUMNS_TO_FILL,
    MOS_OTT_DESIRED_ORDER,
    MOS_OTT_MEAN_COLS,
)

class MOSOTTAggregator:
    def __init__(self, mcc_mnc_df: pd.DataFrame | None = None, test_case_df : pd.DataFrame | None = None):
        self.mcc_mnc_df = mcc_mnc_df
        self.test_case_df = test_case_df

    def _load_file(self, file_obj, filename: str) -> pd.DataFrame | None:
        try:
            df = pd.read_excel(file_obj)

            # MCC/MNC fill
            for col in ("MCC", "MNC"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                    first_nonnull = (
                        df[col].dropna().iloc[0] if not df[col].dropna().empty else None
                    )
                    df[col] = df[col].fillna(first_nonnull)

            # Parse from filename
            base = filename.rsplit(".", 1)[0]
            parts = base.split("_")
            df["Country"] = parts[1] if len(parts) > 1 else "Unknown"
            df["Operator1"] = parts[3] if len(parts) > 3 else "Unknown"
            df["Test Name"] = (
                f"{parts[2][-3:]}_{parts[3]}" if len(parts) > 3 else "Unknown"
            )

            # Side from IMSI marker in filename
            m = re.search(r"IMSI[_\-]?\s*0*(\d+)", base, flags=re.IGNORECASE)
            if m:
                n = m.group(1)
                df["Side"] = (
                    "Side A" if n == "1" else ("Side B" if n == "2" else f"IMSI{n}")
                )
            else:
                df["Side"] = None

            # Type Mobility
            if "BMTT" in base:
                df["Type Mobility"] = "Test Train"
            elif "BMWT" in base:
                df["Type Mobility"] = "Walk Test"
            elif "BMDT" in base:
                df["Type Mobility"] = "Drive Test"
            else:
                df["Type Mobility"] = "Unknown"

            df["__source_file__"] = filename
            logger.info(f"Loaded: {filename}")
            return df
        except Exception as e:
            logger.error(f"Failed to read {filename}: {e}")
            return None

    @staticmethod
    def _numeric_cast(df: pd.DataFrame) -> pd.DataFrame:
        for col in MOS_OTT_MEAN_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    @staticmethod
    def _evaluate_qualification(row: pd.Series) -> str:
        call_status = str(row.get("Call_Status", "")).strip()
        mos = row.get("SQ_MOS")
        if (
            call_status == "Failed"
            or call_status == ""
            or pd.isna(call_status)
            or pd.isna(mos)
            or (isinstance(mos, (float, int)) and mos < 1.3)
        ):
            return "Not Qualified"
        if call_status == "Success" and isinstance(mos, (float, int)) and mos > 1.3:
            return "Qualified"
        return "Not Qualified"

    def process(self, files: List[Tuple[BytesIO, str]]) -> dict[str, BytesIO]:
        # Load
        with ThreadPoolExecutor(max_workers=4) as ex:
            df_list = list(ex.map(lambda f: self._load_file(*f), files))
        df_list = [d for d in df_list if d is not None]
        if not df_list:
            raise ValueError("No MOS OTT raw files loaded.")
        df = pd.concat(df_list, ignore_index=True)

        # Ensure column exists
        if "VoiceLogfileName" not in df.columns:
            df["VoiceLogfileName"] = None

        # Segment sessions by (Side, Operator1), backfill VoiceLogfileName upward until DeviceDescription
        df["Test Id"] = None
        df["VoiceLogfileName_filled"] = None

        for (side_name, operator), grp in df.groupby(
            ["Side", "Operator1"], dropna=False
        ):
            test_id_counter = 1
            for i in grp.index:
                if pd.notnull(df.loc[i, "VoiceLogfileName"]):
                    vlog = df.loc[i, "VoiceLogfileName"]
                    seg_rows = []
                    j = i
                    while j >= grp.index.min():
                        if (
                            df.loc[j, "Side"] != side_name
                            or df.loc[j, "Operator1"] != operator
                        ):
                            break
                        seg_rows.append(j)
                        if "DeviceDescription" in df.columns and pd.notnull(
                            df.loc[j, "DeviceDescription"]
                        ):
                            break
                        j -= 1
                    if not seg_rows:
                        continue
                    for idx in seg_rows:
                        df.at[idx, "VoiceLogfileName_filled"] = vlog
                        df.at[idx, "Test Id"] = f"Test {test_id_counter}"
                    test_id_counter += 1

        # index_id for rows with AQM Score (per Test Id, Side)
        df["index_id"] = None
        for (tid, side), grp in df.groupby(["Test Id", "Side"], dropna=False):
            valid = (
                grp["AQM Score"].notnull()
                if "AQM Score" in grp.columns
                else pd.Series(False, index=grp.index)
            )
            idx = grp[valid].index
            df.loc[idx, "index_id"] = range(1, len(idx) + 1)

        # backfill index_id within (Test Id, Side)
        for (tid, side), grp in df.groupby(["Test Id", "Side"], dropna=False):
            gi = grp.index
            df.loc[gi, "index_id"] = df.loc[gi, "index_id"].bfill()

        # forward/backward fill within groups
        for col in MOS_OTT_COLUMNS_TO_FILL:
            if col in df.columns:
                df[col] = df.groupby(
                    ["Test Id", "VoiceLogfileName_filled"], dropna=False
                )[col].ffill()

        for col in MOS_OTT_COLUMNS_AFTER_FFILL:
            if col in df.columns:
                df[col] = df.groupby(
                    ["Test Id", "VoiceLogfileName_filled"], dropna=False
                )[col].bfill()

        # numeric cast
        df = self._numeric_cast(df)

        # reduce agg rules to available columns
        agg_rules = {k: v for k, v in MOS_OTT_AGG_RULES.items() if k in df.columns}

        # aggregate
        agg_df = (
            df.groupby(["VoiceLogfileName_filled", "Test Id", "index_id"], dropna=True)
            .agg(agg_rules)
            .reset_index()
        )

        # MCC/MNC → Operator
        if self.mcc_mnc_df is not None and {"MCC", "MNC"}.issubset(agg_df.columns):
            try:
                agg_df[["MCC", "MNC"]] = agg_df[["MCC", "MNC"]].astype(int)
                agg_df = agg_df.merge(
                    self.mcc_mnc_df[["MCC", "MNC", "Operator"]],
                    on=["MCC", "MNC"],
                    how="left",
                )
                agg_df["Operator"] = agg_df["Operator"].fillna("Unknown")
            except Exception as e:
                logger.warning(f"MCC/MNC mapping failed: {e}")

        # Sequence (Austria/Bremen only)
        def _seq(row: pd.Series) -> Any:
            if str(row.get("Country", "")).strip() not in {"Austria", "Bremen"}:
                return None
            m = re.search(r"(OTT_\d+)", str(row.get("VoiceLogfileName_filled", "")))
            return m.group(1) if m else None

        agg_df["Sequence"] = agg_df.apply(_seq, axis=1)

        # qualifier
        agg_df["Qualifier"] = agg_df.apply(self._evaluate_qualification, axis=1)

        # rename + sort + reorder
        agg_df = agg_df.rename(columns={"VoiceLogfileName_filled": "VoiceLogfileName"})
        if "Side" in agg_df.columns and "Date Time" in agg_df.columns:
            agg_df = agg_df.sort_values(by=["Side", "Date Time"])
        cols = [c for c in MOS_OTT_DESIRED_ORDER if c in agg_df.columns]
        if cols:
            agg_df = agg_df[cols]

        # to memory per country
        if "Country" not in agg_df.columns:
            raise ValueError("'Country' column is missing before exporting.")

        outputs: dict[str, BytesIO] = {}
        for country, g in agg_df.groupby("Country"):
            buf = BytesIO()
            g.to_excel(buf, index=False)
            buf.seek(0)
            safe = str(country).replace("/", "-").replace(" ", "_")
            outputs[safe] = buf
        return outputs


if __name__ == "__main__":
    import os

    try:
        mcc_mnc_df = pd.read_excel("mncmcc_maping.xlsx")
    except FileNotFoundError:
        mcc_mnc_df = None

    input_folder = "./input_ott_files"
    files = []
    if os.path.isdir(input_folder):
        for fname in os.listdir(input_folder):
            if fname.endswith(".xlsx") and "MOS_OTT" in fname and "clean" not in fname:
                files.append((open(os.path.join(input_folder, fname), "rb"), fname))

    agg = MOSOTTAggregator(mcc_mnc_df)
    outputs = agg.process(files)

    for country, buf in outputs.items():
        out = f"MOS_OTT_{country}_clean.xlsx"
        with open(out, "wb") as f:
            f.write(buf.read())
        logger.info(f"Saved: {out}")
