from __future__ import annotations
from io import BytesIO
from pathlib import Path
from typing import Dict, Iterable, Tuple

import pandas as pd
from loguru import logger

from .split_n_cleansing_config import (
    MOS_OTT_RENAME_MAP,
    MOS_OTT_SCHEMA_GROUPS,
    TEST_NAME_CODES,
    OPERATOR_CODES
)

from .utils import mos_generate_test_ids, reorder_columns_strict

class MOSOTTPackager:
    def __init__(self):
        self.schema_key = "MOSOTT"

    def process(self, files: Iterable[Tuple[object, str]]) -> Dict[str, BytesIO]:
        df_list = []

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

        # Split Date/Time
        if "Date Time" not in df.columns:
            raise ValueError("'Date Time' column missing")
        date_split = df["Date Time"].astype(str).str.split(" ", expand=True)
        date_split.columns = ["Date", "Time"]
        df = pd.concat([df.drop(columns=["Date Time"]), date_split], axis=1)

        # Add End Lat/Lon
        df["End Latitude"] = df["Latitude"]
        df["End Longitude"] = df["Longitude"]

        # Split by Side
        df_a = df[df["Side"] == "Side A"].reset_index(drop=True)
        df_b = df[df["Side"] == "Side B"].reset_index(drop=True)

        if df_a.empty or df_b.empty:
            raise ValueError("Missing Side A or Side B data.")

        merged_df = pd.merge(df_a, df_b, on=["Test Id", "index_id"], suffixes=("", "_B"))

        # Rename columns
        merged_df.rename(columns=MOS_OTT_RENAME_MAP, inplace=True)

        # Generate Test_IDs
        merged_df = mos_generate_test_ids(merged_df, TEST_NAME_CODES, OPERATOR_CODES)

        # Reorder and filter
        df_final = reorder_columns_strict(merged_df, MOS_OTT_SCHEMA_GROUPS, self.schema_key)
        df_final = df_final[
            df_final["Qualifier (SQ MOS A)"].notna() & (df_final["Qualifier (SQ MOS A)"].astype(str).str.strip() != "") &
            df_final["Qualifier (SQ MOS B)"].notna() & (df_final["Qualifier (SQ MOS B)"].astype(str).str.strip() != "")
        ]

        if df_final.empty:
            raise ValueError("No valid data after filtering by Qualifiers.")

        # Export to BytesIO
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_final.to_excel(writer, sheet_name="AllData", index=False)
        output.seek(0)

        # Generate output filename
        first_row = df_final.iloc[0]
        raw_date = pd.to_datetime(first_row.get("Date", pd.NaT), errors='coerce')
        date_str = raw_date.strftime("%Y%m%d") if not pd.isna(raw_date) else "UnknownDate"
        country = str(first_row.get("Route Name", "UnknownCountry")).replace(" ", "_")
        out_name = f"{date_str}_{country}_BM_CDRMOS_OTT.xlsx"

        return {out_name: output}

