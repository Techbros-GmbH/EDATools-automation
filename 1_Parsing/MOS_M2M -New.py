import re
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import Any, List, Tuple

import pandas as pd
from loguru import logger
from parsing_config import (
    MOS_M2M_AGG_RULES,
    MOS_M2M_COLS_AFTER_FFILL,
    MOS_M2M_COLUMNS_TO_FILL,
    MOS_M2M_DESIRED_ORDER,
    MOS_M2M_MEAN_COLS,
)

class M2MAggregator:
    def __init__(self, mcc_mnc_df: pd.DataFrame | None = None):
        self.mcc_mnc_df = mcc_mnc_df

    @staticmethod
    def _extract_side_from_basename(base_name: str) -> str | None:
        m = re.search(r"IMSI[_\-]?\s*0*(\d+)", base_name, flags=re.IGNORECASE)
        if not m:
            return None
        n = m.group(1)
        if n == "1":
            return "Side A"
        if n == "2":
            return "Side B"
        return f"IMSI{n}"

    @staticmethod
    def _safe_numeric_cast(df: pd.DataFrame) -> pd.DataFrame:
        for col in MOS_M2M_MEAN_COLS:
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

    def _load_file(self, file_obj, filename: str) -> pd.DataFrame | None:
        try:
            df = pd.read_excel(file_obj)

            # MCC / MNC fill
            for col in ("MCC", "MNC"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                    first_val_nonnull = (
                        df[col].dropna().iloc[0] if not df[col].dropna().empty else None
                    )
                    df[col] = df[col].fillna(first_val_nonnull)

            # Basic name parsing
            base_name = filename.rsplit(".", 1)[0]
            parts = base_name.split("_")
            df["Country"] = parts[1] if len(parts) > 1 else "Unknown"
            df["Operator1"] = parts[3] if len(parts) > 3 else "Unknown"
            df["Test Name"] = (
                f"{parts[2][-3:]}_{parts[3]}" if len(parts) > 3 else "Unknown"
            )

            # Side from filename
            df["Side"] = self._extract_side_from_basename(base_name)

            # Type Mobility
            if "BMTT" in base_name:
                df["Type Mobility"] = "Test Train"
            elif "BMWT" in base_name:
                df["Type Mobility"] = "Walk Test"
            elif "BMDT" in base_name:
                df["Type Mobility"] = "Drive Test"
            else:
                df["Type Mobility"] = "Unknown"

            df["__source_file__"] = filename
            logger.info(f"Loaded: {filename}")
            return df
        except Exception as e:
            logger.error(f"Failed to read {filename}: {e}")
            return None

    def process(self, files: List[Tuple[BytesIO, str]]) -> dict[str, BytesIO]:
        """
        files: list of (file_obj, filename)
        returns: {country: BytesIO excel}
        """
        # Load all files
        with ThreadPoolExecutor(max_workers=4) as ex:
            df_list = list(ex.map(lambda f: self._load_file(*f), files))
        df_list = [d for d in df_list if d is not None]
        if not df_list:
            raise ValueError("No MOS M2M raw files loaded.")

        df = pd.concat(df_list, ignore_index=True)

        # Prepare columns we will use
        if "VoiceLogfileName" not in df.columns:
            df["VoiceLogfileName"] = None

        # --------- segmentation (per Side + Operator1) ---------
        df["Test Id"] = None
        df["VoiceLogfileName_filled"] = None

        for (side_name, operator), group in df.groupby(
            ["Side", "Operator1"], dropna=False
        ):
            test_id_counter = 1
            for i in group.index:
                voicelog = df.loc[i, "VoiceLogfileName"]
                if pd.notnull(voicelog):
                    # walk backwards inside this (Side, Operator1) chunk until DeviceDescription
                    segment_rows = []
                    j = i
                    while j >= group.index.min():
                        if (
                            df.loc[j, "Side"] != side_name
                            or df.loc[j, "Operator1"] != operator
                        ):
                            break
                        segment_rows.append(j)
                        if "DeviceDescription" in df.columns and pd.notnull(
                            df.loc[j, "DeviceDescription"]
                        ):
                            break
                        j -= 1
                    if not segment_rows:
                        continue

                    for idx in segment_rows:
                        df.at[idx, "VoiceLogfileName_filled"] = voicelog
                        df.at[idx, "Test Id"] = f"Test {test_id_counter}"
                    test_id_counter += 1

        # index_id assignment where AQM Score not null, per (Test Id, Side)
        df["index_id"] = None
        for (test_id, side), group in df.groupby(["Test Id", "Side"], dropna=False):
            valid = (
                group["AQM Score"].notnull()
                if "AQM Score" in group.columns
                else pd.Series(False, index=group.index)
            )
            idx = group[valid].index
            df.loc[idx, "index_id"] = range(1, len(idx) + 1)

        # backfill index_id within (Test Id, Side)
        for (test_id, side), group in df.groupby(["Test Id", "Side"], dropna=False):
            gi = group.index
            df.loc[gi, "index_id"] = df.loc[gi, "index_id"].bfill()

        # forward/backward fill within groups

        for col in MOS_M2M_COLUMNS_TO_FILL:
            if col in df.columns:
                df[col] = df.groupby(
                    ["Test Id", "VoiceLogfileName_filled"], dropna=False
                )[col].ffill()

        for col in MOS_M2M_COLS_AFTER_FFILL:
            if col in df.columns:
                df[col] = df.groupby(
                    ["Test Id", "VoiceLogfileName_filled"], dropna=False
                )[col].bfill()

        # numeric cast for mean cols
        df = self._safe_numeric_cast(df)

        # reduce agg rules to available columns
        agg_rules = {k: v for k, v in MOS_M2M_AGG_RULES.items() if k in df.columns}

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

        # Sequence (Austria/Bremen)
        def _seq(row: pd.Series) -> Any:
            if str(row.get("Country", "")).strip() not in {"Austria", "Bremen"}:
                return None
            m = re.search(r"(Voice_\d+)", str(row.get("VoiceLogfileName_filled", "")))
            return m.group(1) if m else None

        agg_df["Sequence"] = agg_df.apply(_seq, axis=1)

        # qualifier
        agg_df["Qualifier"] = agg_df.apply(self._evaluate_qualification, axis=1)

        # rename + reorder
        agg_df = agg_df.rename(columns={"VoiceLogfileName_filled": "VoiceLogfileName"})
        columns = [c for c in MOS_M2M_DESIRED_ORDER if c in agg_df.columns]
        if columns:
            agg_df = agg_df[columns]

        # export to memory per country
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

    input_folder = "./input_m2m_files"
    files = []
    if os.path.isdir(input_folder):
        for fname in os.listdir(input_folder):
            if fname.endswith(".xlsx") and "MOS_M2M" in fname and "clean" not in fname:
                files.append((open(os.path.join(input_folder, fname), "rb"), fname))

    agg = M2MAggregator(mcc_mnc_df)
    outputs = agg.process(files)

    for country, buf in outputs.items():
        out = f"MOS_M2M_{country}_clean.xlsx"
        with open(out, "wb") as f:
            f.write(buf.read())
        logger.info(f"Saved: {out}")
