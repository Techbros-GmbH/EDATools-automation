import re
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import Any, Iterable, Tuple

import pandas as pd
from loguru import logger
from .parsing_config import (
    STREAMING_AGG_RULES,
    STREAMING_DESIRED_ORDER,
    STREAMING_MEAN_COLS,
)


class StreamingAggregator:
    """
    Build clean Streaming outputs per country (in-memory Excel files).
    - No folder paths needed: pass a list of (file_obj, filename).
    - Uses parsing_config for desired order, mean cols, and agg rules.
    - Optionally merges Operator via MCC/MNC map and Test Name via test-case map.

    files: Iterable[Tuple[file_like, filename]]
           e.g. [(open("Streaming_AT_BMDT_...xlsx","rb"), "Streaming_AT_BMDT_...xlsx"), ...]
    Returns: dict[str, BytesIO] mapping country -> Excel bytes
    """

    def __init__(
        self,
        mcc_mnc_df: pd.DataFrame | None = None,
        test_case_df: pd.DataFrame | None = None,
    ):
        self.mcc_mnc_df = mcc_mnc_df
        self.test_case_df = test_case_df

    def _load_file(self, file_obj, filename: str) -> pd.DataFrame | None:
        try:
            df = pd.read_excel(file_obj)

            # Fill numeric IDs if present
            if "MNC" in df.columns:
                df["MNC"] = pd.to_numeric(df["MNC"], errors="coerce")
                first_mnc = (
                    df["MNC"].dropna().iloc[0] if not df["MNC"].dropna().empty else None
                )
                df["MNC"] = df["MNC"].fillna(first_mnc)

            # Extract Country from filename
            base_name = filename.rsplit(".", 1)[0]
            parts = base_name.split("_")
            df["Country"] = parts[1] if len(parts) > 1 else "Unknown"

            # Type Mobility from filename
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

    @staticmethod
    def _numeric_cast(df: pd.DataFrame) -> pd.DataFrame:
        for col in STREAMING_MEAN_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    @staticmethod
    def _convert_time_to_datetime(val: Any):
        """
        Convert Excel/str/time-like to pandas Timestamp (or None).
        """
        if pd.isna(val):
            return None
        if isinstance(val, pd.Timestamp):
            return val
        # Excel "time" may arrive as datetime.time
        if hasattr(val, "hour") and hasattr(val, "minute") and not hasattr(val, "year"):
            # combine with a dummy date
            return pd.Timestamp.combine(pd.Timestamp(2000, 1, 1), val)  # type: ignore
        try:
            return pd.to_datetime(val, errors="coerce")
        except Exception:
            return None

    @staticmethod
    def _extract_sequence_from_logname(filename: str | None) -> str | None:
        if not filename:
            return None
        m = re.search(r"EQ1_Data_(TRP\d+_\d+)_MS\d+", str(filename))
        return m.group(1) if m else None

    @staticmethod
    def _qualifier_rule(row: pd.Series) -> str:
        # Based on "Test Name" (from test-case map) + streaming KPIs
        play_pic = row.get("Play Request to 1st Picture")
        stream_acc = row.get("Streaming_Service_Access_Time_sec")
        interruptions = row.get("Streaming_Number_Of_Video_Session_Interruptions")

        try:
            play_pic = float(play_pic) if play_pic not in (None, "N/A") else 0.0
        except Exception:
            play_pic = 0.0
        try:
            stream_acc = float(stream_acc) if pd.notna(stream_acc) else 0.0
        except Exception:
            stream_acc = 0.0
        try:
            interruptions = float(interruptions) if pd.notna(interruptions) else 0.0
        except Exception:
            interruptions = 0.0

        name = str(row.get("Test Name", "")).upper().strip()
        if name in {"YOUTUBELIVE", "YOUTUBE VOD"}:
            if stream_acc > 10 or play_pic > 10 or interruptions > 0:
                return "Not Qualified"
        return "Qualified"

    def process(self, files: Iterable[Tuple[object, str]]) -> dict[str, BytesIO]:
        # Step 1: Load
        with ThreadPoolExecutor(max_workers=len(files)) as ex:
            df_list = list(ex.map(lambda f: self._load_file(*f), files))
        df_list = [d for d in df_list if d is not None]
        if not df_list:
            raise ValueError("No Streaming raw files loaded.")
        df = pd.concat(df_list, ignore_index=True)

        # Step 2: Forward-fill Streaming_URL and segment on StreamingServiceStatus
        if "Streaming_URL" in df.columns:
            df["Streaming_URL"] = df["Streaming_URL"].ffill()
            if "StreamingServiceStatus" in df.columns:
                segment = df["StreamingServiceStatus"].notnull().cumsum()
                df["Streaming_URL"] = df.groupby(segment)["Streaming_URL"].ffill()
                mask = (
                    df["StreamingServiceStatus"].notnull()
                    & df["Streaming_URL"].isnull()
                )
                df.loc[mask, "Streaming_URL"] = df["Streaming_URL"].ffill()

        # Step 3: Assign Test Id by URL segments
        if "Streaming_URL" in df.columns:
            is_new_test = (df["Streaming_URL"] != df["Streaming_URL"].shift(1)) & df[
                "Streaming_URL"
            ].notnull()
            df["Test Id"] = is_new_test.cumsum().where(df["Streaming_URL"].notnull())
            df["Test Id"] = df["Test Id"].apply(
                lambda x: f"Test {int(x)}" if pd.notnull(x) else None
            )
        else:
            df["Test Id"] = None

        # Step 4: Numeric casting for mean columns
        df = self._numeric_cast(df)

        # Step 5: Aggregate per (Streaming_URL, Test Id)
        agg_df = (
            df.groupby(["Streaming_URL", "Test Id"], dropna=True)
            .agg(STREAMING_AGG_RULES)
            .reset_index()
        )

        # Add Stop Date Time (last Date Time in each group)
        if "Date Time" in df.columns:
            stop_dates = (
                df.groupby(["Streaming_URL", "Test Id"], dropna=True)["Date Time"]
                .last()
                .reset_index()
                .rename(columns={"Date Time": "Stop Date Time"})
            )
            agg_df = agg_df.merge(
                stop_dates, on=["Streaming_URL", "Test Id"], how="left"
            )

        # Optional: Operator mapping via Country + MNC
        if self.mcc_mnc_df is not None and {"Country", "MNC"}.issubset(agg_df.columns):
            try:
                map_df = self.mcc_mnc_df.copy()
                # normalize types
                map_df["MNC"] = (
                    pd.to_numeric(map_df["MNC"], errors="coerce")
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
                map_df["Country"] = map_df["Country"].astype(str).str.strip()
                agg_df["Country"] = agg_df["Country"].astype(str).str.strip()

                agg_df = agg_df.merge(
                    map_df[["Country", "MNC", "Operator"]],
                    on=["Country", "MNC"],
                    how="left",
                    suffixes=("", "_map"),
                )
                # Fill Operator (create or fill missing)
                if "Operator" in agg_df.columns:
                    agg_df["Operator"] = agg_df["Operator"].fillna(
                        agg_df["Operator_map"]
                    )
                else:
                    agg_df["Operator"] = agg_df["Operator_map"]
                agg_df.drop(
                    columns=[c for c in ["Operator_map"] if c in agg_df.columns],
                    inplace=True,
                )
                logger.info("Operator mapping applied.")
            except Exception as e:
                logger.warning(f"Operator mapping failed: {e}")

        # Optional: Test Name mapping (HTTP_URL + Country) — original script behavior
        if self.test_case_df is not None:
            try:
                agg_df = agg_df.rename(columns={"Streaming_URL": "HTTP_URL"})
                if {"HTTP_URL", "Country"}.issubset(agg_df.columns) and {
                    "HTTP_URL",
                    "Country",
                    "Test Name",
                }.issubset(self.test_case_df.columns):
                    agg_df = agg_df.merge(
                        self.test_case_df[["HTTP_URL", "Country", "Test Name"]],
                        on=["HTTP_URL", "Country"],
                        how="left",
                    )
                    agg_df["Test Name"] = agg_df["Test Name"].fillna("Not_found")
                    logger.info("Test Name mapping applied.")
                else:
                    logger.warning("Test map missing required columns.")
            except Exception as e:
                logger.warning(f"Test Name mapping failed: {e}")
            finally:
                agg_df = agg_df.rename(columns={"HTTP_URL": "Streaming_URL"})

        # Compute "Play Request to 1st Picture" (seconds)
        if {"StreamingStatePlayerRequestTime", "StreamingStartTime"}.issubset(
            agg_df.columns
        ):
            try:
                a = agg_df["StreamingStatePlayerRequestTime"].map(
                    self._convert_time_to_datetime
                )
                b = agg_df["StreamingStartTime"].map(self._convert_time_to_datetime)
                delta = (a - b).dt.total_seconds()
                agg_df["Play Request to 1st Picture"] = delta.round(3).where(
                    delta.notna(), "N/A"
                )
            except Exception as e:
                logger.warning(f"Could not compute 'Play Request to 1st Picture': {e}")
                agg_df["Play Request to 1st Picture"] = "N/A"
        else:
            agg_df["Play Request to 1st Picture"] = "N/A"

        # Sequence for Austria/Bremen
        if "StreamingLogfileName" in agg_df.columns:
            agg_df["Sequence"] = agg_df.apply(
                lambda row: self._extract_sequence_from_logname(
                    row["StreamingLogfileName"]
                )
                if row.get("Country") in ["Austria", "Bremen"]
                else None,
                axis=1,
            )

        # Qualifier
        agg_df["Qualifier"] = agg_df.apply(self._qualifier_rule, axis=1)

        # Reorder columns (keep only those present)
        cols_present = [c for c in STREAMING_DESIRED_ORDER if c in agg_df.columns]
        agg_df = agg_df[cols_present]

        # Export per Country to memory
        if "Country" not in agg_df.columns:
            raise ValueError("'Country' column is missing before exporting.")

        output_files: dict[str, BytesIO] = {}
        for country, group_df in agg_df.sort_values(by=cols_present[0]).groupby(
            "Country"
        ):
            buf = BytesIO()
            group_df.to_excel(buf, index=False)
            buf.seek(0)
            output_files[country] = buf

        return output_files


if __name__ == "__main__":
    import os

    logger.add("streaming_aggregator.log", rotation="1 MB")
    try:
        mcc_mnc_df = pd.read_excel("mncmcc_maping.xlsx")
    except FileNotFoundError:
        mcc_mnc_df = None

    try:
        test_case_df = pd.read_excel("test case map.xlsx")
    except FileNotFoundError:
        test_case_df = None

    # Collect input files from a folder for quick testing
    input_folder = "./input_streaming_files"
    files: list[Tuple[object, str]] = []
    if os.path.isdir(input_folder):
        for fname in os.listdir(input_folder):
            if (
                fname.endswith(".xlsx")
                and "Streaming" in fname
                and "clean" not in fname
            ):
                files.append((open(os.path.join(input_folder, fname), "rb"), fname))
    else:
        logger.warning(f"Folder not found: {input_folder}")

    if not files:
        logger.error("No input files found for demo run.")
    else:
        agg = StreamingAggregator(mcc_mnc_df=mcc_mnc_df, test_case_df=test_case_df)
        outputs = agg.process(files)
        for country, buf in outputs.items():
            out_path = f"Streaming_{country}_clean.xlsx"
            with open(out_path, "wb") as f:
                f.write(buf.read())
            logger.info(f"Saved: {out_path}")
