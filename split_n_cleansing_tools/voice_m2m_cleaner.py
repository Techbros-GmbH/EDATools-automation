from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Dict, Iterable, Tuple

import pandas as pd
from loguru import logger
from .split_n_cleansing_config import (
    OPERATOR_CODES,
    TEST_NAME_CODES,
    VOICE_M2M_RENAME_MAP,
    VOICE_M2M_SCHEMA_GROUPS,
)
from .utils import (
    mos_generate_test_ids,
    reorder_columns_strict,
)


class VoiceM2MPackager:
    def __init__(self):
        self.schema_key = "VoiceM2M"

    def process(self, files: Iterable[Tuple[object, str]]) -> Dict[str, BytesIO]:
        df_list = []

        # === Load all files
        for fobj, fname in files:
            try:
                df = pd.read_excel(fobj, sheet_name=0)
                df["SourceFile"] = Path(fname).stem
                df_list.append(df)
                logger.info(f"Loaded: {fname}")
            except Exception as e:
                logger.warning(f"Skipping {fname}: {e}")

        if not df_list:
            raise ValueError("No input files loaded.")

        df = pd.concat(df_list, ignore_index=True)
        df.columns = df.columns.str.strip()

        # === Split Date and Time
        if "Date Time" not in df.columns:
            raise ValueError("'Date Time' column not found in input data.")
        date_split = df["Date Time"].astype(str).str.split(" ", expand=True)
        if date_split.shape[1] != 2:
            raise ValueError("Unable to split 'Date Time' into Date and Time.")
        date_split.columns = ["Date", "Time"]
        df = pd.concat([df.drop(columns=["Date Time"]), date_split], axis=1)

        # === Duplicate Lat/Lon to End Lat/Lon (pre-merge)
        if "Latitude" in df.columns and "End Latitude" not in df.columns:
            df["End Latitude"] = df["Latitude"]
        if "Longitude" in df.columns and "End Longitude" not in df.columns:
            df["End Longitude"] = df["Longitude"]

        # === Split by Side
        if "Side" not in df.columns:
            raise ValueError("'Side' column missing from input.")
        if "Pair_ID" not in df.columns:
            raise ValueError("'Pair_ID' column missing from input.")

        side_a_df = df[df["Side"] == "Side A"].reset_index(drop=True)
        side_b_df = df[df["Side"] == "Side B"].reset_index(drop=True)
        if side_a_df.empty or side_b_df.empty:
            raise ValueError("Side A or Side B data is missing from input.")

        # === Merge A and B on Pair_ID
        merged_df = pd.merge(
            side_a_df,
            side_b_df,
            on="Pair_ID",
            how="left",
            suffixes=("", "_B"),
        )

        # === Rename columns globally
        merged_df.rename(columns=VOICE_M2M_RENAME_MAP, inplace=True)
        merged_df.columns = merged_df.columns.str.strip()

        # === Generate Test_IDs (same scheme as your original)
        merged_df = mos_generate_test_ids(merged_df, TEST_NAME_CODES, OPERATOR_CODES)

        # === Reorder strictly by schema
        df_final = reorder_columns_strict(
            merged_df, VOICE_M2M_SCHEMA_GROUPS, self.schema_key
        )

        if df_final.empty:
            raise ValueError("No rows after schema selection.")

        # === Export to memory (single file, AllData sheet)
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_final.to_excel(writer, sheet_name="AllData", index=False)
        output.seek(0)

        # === Filename
        first_row = df_final.iloc[0]
        raw_date = pd.to_datetime(first_row.get("Date", pd.NaT), errors="coerce")
        date_str = (
            raw_date.strftime("%Y%m%d") if not pd.isna(raw_date) else "UnknownDate"
        )
        country = str(first_row.get("Route Name", "UnknownCountry")).replace(" ", "_")
        out_name = f"{date_str}_{country}_BM_CDRVoice_M2M.xlsx"

        return {out_name: output}


if __name__ == "__main__":
    # Set input/output folders
    input_folder = Path(
        "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/split/Voice_M2M/Input"
    )
    output_folder = Path(
        "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/split/Voice_M2M/Output2"
    )
    output_folder.mkdir(parents=True, exist_ok=True)

    # Load all .xlsx files from the input directory
    files = []
    for file_path in input_folder.glob("*.xlsx"):
        try:
            with open(file_path, "rb") as f:
                data = f.read()
            files.append((BytesIO(data), file_path.name))
        except Exception as e:
            logger.warning(f"❌ Could not open file {file_path.name}: {e}")

    # Run the packager
    if not files:
        logger.error("❌ No input files found.")
    else:
        packager = VoiceM2MPackager()
        results = packager.process(files)

        for filename, buffer in results.items():
            output_path = output_folder / filename
            with open(output_path, "wb") as f:
                f.write(buffer.getbuffer())
            logger.success(f"✅ Saved: {output_path}")
