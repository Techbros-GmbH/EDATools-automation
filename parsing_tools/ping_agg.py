import re
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import List, Tuple

import pandas as pd
from loguru import logger
from .parsing_config import (
    PING_AGG_RULES,
    PING_DESIRED_ORDER,
    PING_MEAN_COLS,
)


class PingAggregator:
    def __init__(self, mcc_mnc_df: pd.DataFrame | None = None, test_case_df: pd.DataFrame | None =None):
        self.mcc_mnc_df = mcc_mnc_df
        self.test_case_df = test_case_df

    def _load_file(self, file_obj, filename: str) -> pd.DataFrame | None:
        try:
            df = pd.read_excel(file_obj)

            # Fill IMSI (per file)
            if "IMSI" in df.columns:
                df["IMSI"] = pd.to_numeric(df["IMSI"], errors="coerce")
                first_imsi = (
                    df["IMSI"].dropna().iloc[0]
                    if not df["IMSI"].dropna().empty
                    else None
                )
                df["IMSI"] = df["IMSI"].fillna(first_imsi)

            # Fill Operator (per file)
            if "Operator" in df.columns:
                first_op = (
                    df["Operator"].dropna().iloc[0]
                    if not df["Operator"].dropna().empty
                    else None
                )
                df["Operator"] = df["Operator"].fillna(first_op)

            # From filename: Country + Mobility
            base = filename.rsplit(".", 1)[0]
            parts = base.split("_")
            df["Country"] = parts[1] if len(parts) > 1 else "Unknown"

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
        for col in PING_MEAN_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    @staticmethod
    def _map_test_name(size) -> str:
        try:
            s = int(size)
            return f"Ping {s}"
        except Exception:
            return "Ping Unknown"

    def process(self, files: List[Tuple[BytesIO, str]]) -> dict[str, BytesIO]:
        # Load all files
        with ThreadPoolExecutor(max_workers=4) as ex:
            df_list = list(ex.map(lambda f: self._load_file(*f), files))
        df_list = [d for d in df_list if d is not None]
        if not df_list:
            raise ValueError("No Ping raw files loaded.")
        df = pd.concat(df_list, ignore_index=True)

        # Ensure columns exist
        if "PingLogfileName" not in df.columns:
            df["PingLogfileName"] = None
        if "MNC" not in df.columns:
            df["MNC"] = None

        # Step 2: Upward fill PingLogfileName until MNC is found (don't overwrite the MNC row)
        for i in reversed(df.index):
            if pd.notnull(df.loc[i, "PingLogfileName"]):
                j = i - 1
                while j >= 0 and pd.isnull(df.loc[j, "MNC"]):
                    if pd.isnull(df.loc[j, "PingLogfileName"]):
                        df.loc[j, "PingLogfileName"] = df.loc[i, "PingLogfileName"]
                    j -= 1

        # Step 3: Assign Segment ID (start at MNC, continue while PingLogfileName is filled)
        df["Segment ID"] = None
        segment_id = 1
        inside_segment = False
        for idx in df.index:
            if pd.notnull(df.loc[idx, "MNC"]):
                df.at[idx, "Segment ID"] = segment_id
                inside_segment = True
            elif inside_segment and pd.notnull(df.loc[idx, "PingLogfileName"]):
                df.at[idx, "Segment ID"] = segment_id
            elif inside_segment and pd.isnull(df.loc[idx, "PingLogfileName"]):
                inside_segment = False
                segment_id += 1

        # Step 4: Assign Test ID using upward fill logic within Segment
        df["Test ID"] = None
        if "PingStartTime" not in df.columns:
            df["PingStartTime"] = None

        for seg_id, group in df.groupby("Segment ID", dropna=True):
            group = group.sort_index(ascending=True)
            test_id = 1
            indices = list(group.index)

            for i in range(len(indices)):
                idx = indices[i]
                current_time = df.loc[idx, "PingStartTime"]

                if pd.notnull(current_time):
                    df.at[idx, "Test ID"] = test_id
                    # Fill upward inside the same segment until we hit a row with its own start time
                    j = i - 1
                    while (
                        j >= 0
                        and pd.isnull(df.loc[indices[j], "PingStartTime"])
                        and pd.isnull(df.loc[indices[j], "Test ID"])
                    ):
                        df.at[indices[j], "Test ID"] = test_id
                        j -= 1
                    test_id += 1
                elif pd.isnull(df.loc[idx, "Test ID"]):
                    df.at[idx, "Test ID"] = test_id

        # Step 4.5: Forward-fill MNC only when PingLogfileName is not blank and within Segment ID
        for seg_id, group in df.groupby("Segment ID", dropna=True):
            indices = group.index.tolist()
            last_mnc = None
            for idx in indices:
                if pd.notnull(df.at[idx, "MNC"]):
                    last_mnc = df.at[idx, "MNC"]
                elif pd.notnull(df.at[idx, "PingLogfileName"]) and last_mnc is not None:
                    df.at[idx, "MNC"] = last_mnc

        # Numeric cast for mean columns
        df = self._numeric_cast(df)

        # Reduce agg rules to available columns
        agg_rules = {k: v for k, v in PING_AGG_RULES.items() if k in df.columns}

        # Aggregate
        agg_df = (
            df.groupby(["Segment ID", "Test ID"], dropna=True)
            .agg(agg_rules)
            .reset_index()
        )

        # Stop Date Time (last Date Time per group)
        if "Date Time" in df.columns:
            stop_dates = (
                df.groupby(["Segment ID", "Test ID"], dropna=True)["Date Time"]
                .last()
                .reset_index()
                .rename(columns={"Date Time": "Stop Date Time"})
            )
            agg_df = agg_df.merge(stop_dates, on=["Segment ID", "Test ID"], how="left")

        # Sequence (Austria/Bremen only), from PingLogfileName
        def _seq(row: pd.Series):
            if str(row.get("Country", "")).strip() not in {"Austria", "Bremen"}:
                return None
            m = re.search(r"(TRP\d+_\d+)", str(row.get("PingLogfileName", "")))
            return m.group(1) if m else None

        agg_df["Sequence"] = agg_df.apply(_seq, axis=1)

        # Test Name from Ping_Size
        if "Ping_Size" in agg_df.columns:
            agg_df["Test Name"] = agg_df["Ping_Size"].apply(self._map_test_name)

        # Remove rows where PingLogfileName is blank
        if "PingLogfileName" in agg_df.columns:
            agg_df = agg_df[agg_df["PingLogfileName"].notna()]

        # Operator_New mapping (Country + 3-digit MNC)
        if self.mcc_mnc_df is not None and {"MNC", "Country"}.issubset(agg_df.columns):
            try:
                mcc = self.mcc_mnc_df.copy()
                mcc.columns = mcc.columns.str.strip()
                agg_df.columns = agg_df.columns.str.strip()
                logger.debug("mcc_mnc_df sucessfully loaded")

                mcc["MNC"] = (
                    pd.to_numeric(mcc["MNC"], errors="coerce")
                    .fillna(0)
                    .astype(int)
                    .astype(str)
                    .str.zfill(3)
                )
                agg_df["MNC"] = (
                    pd.to_numeric(agg_df["MNC"], errors="coerce")
                    .fillna(0)
                    .astype(int)
                    .astype(str)
                    .str.zfill(3)
                )
                mcc["Country"] = mcc["Country"].astype(str).str.strip()
                agg_df["Country"] = agg_df["Country"].astype(str).str.strip()

                agg_df = agg_df.merge(
                    mcc[["Country", "MNC", "Operator"]].rename(
                        columns={"Operator": "Operator_New"}
                    ),
                    on=["Country", "MNC"],
                    how="left",
                )
                # place Operator_New after Test Name if both exist
                if "Test Name" in agg_df.columns and "Operator_New" in agg_df.columns:
                    cols = list(agg_df.columns)
                    cols.remove("Operator_New")
                    cols.insert(cols.index("Test Name") + 1, "Operator_New")
                    agg_df = agg_df[cols]
                logger.info("Operator_New successfully mapped.")
            except Exception as e:
                logger.warning(f"Operator mapping failed: {e}")
                agg_df["Operator_New"] = "Unknown"

        # Sort + Reorder
        if "Date Time" in agg_df.columns:
            agg_df = agg_df.sort_values(by="Date Time")

        cols = [c for c in PING_DESIRED_ORDER if c in agg_df.columns]
        if cols:
            agg_df = agg_df[cols]

        # Export to memory per Country
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

    # Optional: load MCC/MNC mapping
    try:
        mcc_mnc_df = pd.read_excel("mncmcc_maping.xlsx")
    except FileNotFoundError:
        mcc_mnc_df = None

    # Quick local test runner
    input_folder = "./input_ping_files"
    files: list[tuple[BytesIO, str]] = []
    if os.path.isdir(input_folder):
        for fname in os.listdir(input_folder):
            if fname.endswith(".xlsx") and "Ping" in fname and "clean" not in fname:
                files.append((open(os.path.join(input_folder, fname), "rb"), fname))

    agg = PingAggregator(mcc_mnc_df)
    out_map = agg.process(files)

    for country, buf in out_map.items():
        out_path = f"Ping_{country}_clean.xlsx"
        with open(out_path, "wb") as f:
            f.write(buf.read())
        logger.info(f"Saved: {out_path}")
