# videochat_aggregator.py

import re
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import Any, Iterable, Tuple

import pandas as pd
from loguru import logger
from parsing_config import (
    VIDEOCHAT_AGG_RULES,
    VIDEOCHAT_DESIRED_ORDER,
    VIDEOCHAT_MEAN_COLS,
)


class VideoChatAggregator:
    """
    Build clean Video Chat outputs per country (in-memory Excel files).
    - Pass a list of (file_obj, filename) tuples.
    - Optionally merge Operator via an MCC/MNC dataframe.

    Example 'files' input:
      [(open("Data_VideoChat_AT_BMDT_....xlsx","rb"), "Data_VideoChat_AT_BMDT_....xlsx"), ...]
    Returns:
      dict[country -> BytesIO]
    """

    def __init__(self, mcc_mnc_df: pd.DataFrame | None = None, max_workers: int = 4):
        self.mcc_mnc_df = mcc_mnc_df
        self.max_workers = max_workers

    # ---------- helpers ----------

    def _load_file(self, file_obj, filename: str) -> pd.DataFrame | None:
        try:
            df = pd.read_excel(file_obj)

            # Fill MCC/MNC if present
            if "MCC" in df.columns:
                df["MCC"] = pd.to_numeric(df["MCC"], errors="coerce")
                first_mcc = (
                    df["MCC"].dropna().iloc[0] if not df["MCC"].dropna().empty else None
                )
                df["MCC"] = df["MCC"].fillna(first_mcc)
            if "MNC" in df.columns:
                df["MNC"] = pd.to_numeric(df["MNC"], errors="coerce")
                first_mnc = (
                    df["MNC"].dropna().iloc[0] if not df["MNC"].dropna().empty else None
                )
                df["MNC"] = df["MNC"].fillna(first_mnc)

            # Fill DeviceDescription if present
            if "DeviceDescription" in df.columns:
                first_device = (
                    df["DeviceDescription"].dropna().iloc[0]
                    if not df["DeviceDescription"].dropna().empty
                    else None
                )
                df["DeviceDescription"] = df["DeviceDescription"].fillna(first_device)

            # Country & Test Name from filename
            base_name = filename.rsplit(".", 1)[0]
            parts = base_name.split("_")
            df["Country"] = parts[1] if len(parts) > 1 else "Unknown"
            df["Test Name"] = (
                f"{parts[2][-4:]}_{parts[3]}" if len(parts) > 3 else "Unknown"
            )

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
    def _first_val(x: pd.Series) -> Any:
        x = x.dropna()
        return x.iloc[0] if not x.empty else None

    @staticmethod
    def _last_val(x: pd.Series) -> Any:
        x = x.dropna()
        return x.iloc[-1] if not x.empty else None

    @staticmethod
    def _numeric_cast(df: pd.DataFrame) -> pd.DataFrame:
        for col in VIDEOCHAT_MEAN_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    @staticmethod
    def _extract_sequence(logname: str | None) -> str | None:
        if not logname:
            return None
        m = re.search(r"(TRP\d+_\d+)", str(logname))
        return m.group(1) if m else None

    @staticmethod
    def _qualifier(row: pd.Series) -> str:
        # More robust than the original (handles various typos/variants)
        op_success = (
            (
                row.get("TWAMP Operation Success")
                or row.get("TWAMP Operation Succes")
                or ""
            )
            .strip()
            .lower()
        )
        # Accept anything that starts with "twamp operation success"
        ok = op_success.startswith("twamp operation success")

        rtt_min = row.get("TWAMP_Rtt_Min_ms")
        try:
            rtt_min = float(rtt_min) if pd.notna(rtt_min) else None
        except Exception:
            rtt_min = None

        if ok and (rtt_min is not None) and rtt_min < 100:
            return "Not Qualified"
        return "Qualified"

    # ---------- main ----------

    def process(self, files: Iterable[Tuple[object, str]]) -> dict[str, BytesIO]:
        # Step 1: load
        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            df_list = list(ex.map(lambda f: self._load_file(*f), files))
        df_list = [d for d in df_list if d is not None]
        if not df_list:
            raise ValueError("No Video Chat raw files loaded.")
        df = pd.concat(df_list, ignore_index=True)

        # Step 2: derive Test Id from TWAMP start/end markers
        if {"TWAMP Operation Start", "TWAMP Operation End"}.issubset(df.columns):
            start_idx = df.index[df["TWAMP Operation Start"].notna()].tolist()
            end_idx = df.index[df["TWAMP Operation End"].notna()].tolist()

            df["Test Id"] = None
            seg_pointer = 0
            for s in start_idx:
                e = next((x for x in end_idx if x > s), None)
                if e is not None:
                    df.loc[s:e, "Test Id"] = seg_pointer + 1
                    seg_pointer += 1
        else:
            df["Test Id"] = None

        # Step 3: fill logfile name within each segment
        if "Logfile Name" in df.columns:
            df["Logfile Name"] = df.groupby("Test Id")["Logfile Name"].ffill().bfill()

        # Step 4: numeric cast for mean columns
        df = self._numeric_cast(df)

        # Step 5: aggregate
        agg_df = (
            df.groupby(["Logfile Name", "Test Id"], dropna=True)
            .agg(VIDEOCHAT_AGG_RULES)
            .reset_index()
        )

        # end_latitude / end_longitude
        if {"Latitude", "Longitude"}.issubset(df.columns):
            lat_last = df.groupby(["Logfile Name", "Test Id"])["Latitude"].agg(
                self._last_val
            )
            lon_last = df.groupby(["Logfile Name", "Test Id"])["Longitude"].agg(
                self._last_val
            )
            agg_df["end_latitude"] = lat_last.values
            agg_df["end_longitude"] = lon_last.values

        # Sequence (Austria/Bremen)
        if "Logfile Name" in agg_df.columns:
            agg_df["Sequence"] = agg_df.apply(
                lambda row: self._extract_sequence(row["Logfile Name"])
                if row.get("Country") in ["Austria", "Bremen"]
                else None,
                axis=1,
            )

        # Operator mapping via MCC/MNC
        if self.mcc_mnc_df is not None and {"MCC", "MNC"}.issubset(agg_df.columns):
            try:
                map_df = self.mcc_mnc_df.copy()
                # use ints for both sides (your original script did this)
                map_df[["MCC", "MNC"]] = (
                    map_df[["MCC", "MNC"]]
                    .apply(pd.to_numeric, errors="coerce")
                    .astype("Int64")
                )
                agg_df[["MCC", "MNC"]] = (
                    agg_df[["MCC", "MNC"]]
                    .apply(pd.to_numeric, errors="coerce")
                    .astype("Int64")
                )
                agg_df = agg_df.merge(
                    map_df[["MCC", "MNC", "Operator"]], on=["MCC", "MNC"], how="left"
                )
                agg_df["Operator"] = agg_df["Operator"].fillna("Unknown")
            except Exception as e:
                logger.warning(f"MCC/MNC mapping failed: {e}")

        # Reorder
        cols_present = [c for c in VIDEOCHAT_DESIRED_ORDER if c in agg_df.columns]
        agg_df = agg_df[cols_present] if cols_present else agg_df

        # Sort
        sort_cols = [c for c in ["Test Id", "Date Time"] if c in agg_df.columns]
        if sort_cols:
            agg_df = agg_df.sort_values(by=sort_cols)

        # Qualifier
        agg_df["Qualifier"] = agg_df.apply(self._qualifier, axis=1)

        # Export per-country
        if "Country" not in agg_df.columns:
            raise ValueError("'Country' column is missing before exporting.")

        outputs: dict[str, BytesIO] = {}
        for country, grp in agg_df.groupby("Country"):
            buf = BytesIO()
            grp.to_excel(buf, index=False)
            buf.seek(0)
            outputs[country] = buf

        return outputs


if __name__ == "__main__":
    import os

    try:
        mcc_mnc_df = pd.read_excel("mncmcc_maping.xlsx")
    except FileNotFoundError:
        mcc_mnc_df = None

    input_folder = "./input_videochat_files"
    files: list[Tuple[object, str]] = []
    if os.path.isdir(input_folder):
        for fname in os.listdir(input_folder):
            if (
                fname.endswith(".xlsx")
                and "Data_VideoChat" in fname
                and "clean" not in fname
            ):
                files.append((open(os.path.join(input_folder, fname), "rb"), fname))
    else:
        logger.warning(f"Folder not found: {input_folder}")

    if not files:
        logger.error("No input files found for demo run.")
    else:
        agg = VideoChatAggregator(mcc_mnc_df=mcc_mnc_df)
        outputs = agg.process(files)
        for country, buf in outputs.items():
            out_path = f"Data_VideoChat_{country}_clean.xlsx"
            with open(out_path, "wb") as f:
                f.write(buf.read())
            logger.info(f"Saved: {out_path}")
