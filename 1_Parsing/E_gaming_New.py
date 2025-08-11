import re
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import Any

import pandas as pd
from loguru import logger
from parsing_config import GAMING_AGG_RULES, GAMING_DESIRED_ORDER, GAMING_MEAN_COLS


class EgamingAggregator:
    def __init__(self, mcc_mnc_df=None):
        self.mcc_mnc_df = mcc_mnc_df

    def _load_file(self, file_obj, filename):
        try:
            df = pd.read_excel(file_obj)

            # Fill MCC/MNC
            df["MCC"] = pd.to_numeric(df["MCC"], errors="coerce")
            df["MNC"] = pd.to_numeric(df["MNC"], errors="coerce")
            first_mcc = (
                df["MCC"].dropna().iloc[0] if not df["MCC"].dropna().empty else None
            )
            first_mnc = (
                df["MNC"].dropna().iloc[0] if not df["MNC"].dropna().empty else None
            )
            df["MCC"].fillna(first_mcc, inplace=True)
            df["MNC"].fillna(first_mnc, inplace=True)

            # Fill Device
            first_device = (
                df["DeviceDescription"].dropna().iloc[0]
                if not df["DeviceDescription"].dropna().empty
                else None
            )
            df["DeviceDescription"] = df["DeviceDescription"].fillna(first_device)

            # Extract Country and Test Name from filename
            base_name = filename.rsplit(".", 1)[0]
            parts = base_name.split("_")
            df["Country"] = parts[1] if len(parts) > 1 else "Unknown"
            df["Test Name"] = (
                f"{parts[2][-4:]}_{parts[3]}" if len(parts) > 3 else "Unknown"
            )

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

    def _numeric_cast(self, df):
        for col in GAMING_MEAN_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def _check_qualifier(self, row):
        TWAMPOpSucces = row.get("TWAMP Operation Succes") or 0
        TWAMP_Rtt_Min = row.get("TWAMP_Rtt_Min_ms") or 0
        if TWAMPOpSucces == "TWAMP Operation SuccessL" and TWAMP_Rtt_Min < 100:
            return "Not Qualified"
        return "Qualified"

    def _last_val(self, x: pd.Series) -> Any:
        return x.dropna().iloc[-1] if not x.dropna().empty else None

    def process(self, files):
        # Step 1: Load files
        with ThreadPoolExecutor(max_workers=4) as ex:
            df_list = list(ex.map(lambda f: self._load_file(*f), files))
        df_list = [d for d in df_list if d is not None]
        if not df_list:
            raise ValueError("No EGaming raw files loaded.")

        df = pd.concat(df_list, ignore_index=True)

        # Step 2: Segment Test Id from TWAMP start/end
        start_indices = df.index[df["TWAMP Operation Start"].notna()].tolist()
        end_indices = df.index[df["TWAMP Operation End"].notna()].tolist()

        df["Test Id"] = None
        seg_pointer = 0
        for start in start_indices:
            end = next((e for e in end_indices if e > start), None)
            if end is not None:
                df.loc[start:end, "Test Id"] = seg_pointer + 1
                seg_pointer += 1

        # Fill logfile name
        df["Logfile Name"] = df.groupby("Test Id")["Logfile Name"].ffill().bfill()

        # Step 3: Numeric casting
        df = self._numeric_cast(df)

        # Step 4: Aggregate
        agg_df = (
            df.groupby(["Logfile Name", "Test Id"], dropna=True)
            .agg(GAMING_AGG_RULES)
            .reset_index()
        )

        # Add end lat/lon
        agg_df["end_latitude"] = (
            df.groupby(["Logfile Name", "Test Id"])["Latitude"]
            .agg(self._last_val)
            .values
        )
        agg_df["end_longitude"] = (
            df.groupby(["Logfile Name", "Test Id"])["Longitude"]
            .agg(self._last_val)
            .values
        )

        # Sequence for Austria/Bremen
        agg_df["Sequence"] = agg_df.apply(
            lambda row: re.search(r"(TRP\d+_\d+)", str(row["Logfile Name"])).group(1)
            if row.get("Country") in ["Austria", "Bremen"]
            and re.search(r"(TRP\d+_\d+)", str(row["Logfile Name"]))
            else None,
            axis=1,
        )

        # MCC/MNC mapping
        if self.mcc_mnc_df is not None:
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

        # Step 5: Reorder
        agg_df = agg_df[[col for col in GAMING_DESIRED_ORDER if col in agg_df.columns]]

        # Step 6: Qualifier
        agg_df["Qualifier"] = agg_df.apply(self._check_qualifier, axis=1)

        # Step 7: Export to memory per country
        if "Country" not in agg_df.columns:
            raise ValueError("'Country' column is missing before exporting.")

        output_files = {}
        for country, group_df in agg_df.groupby("Country"):
            buf = BytesIO()
            group_df.to_excel(buf, index=False)
            buf.seek(0)
            output_files[country] = buf

        return output_files


if __name__ == "__main__":
    import os

    # Load mapping if available
    try:
        mcc_mnc_df = pd.read_excel("mncmcc_maping.xlsx")
    except FileNotFoundError:
        mcc_mnc_df = None

    # Folder for testing
    input_folder = "./input_egaming_files"
    files = []
    for fname in os.listdir(input_folder):
        if fname.endswith(".xlsx") and "Data_EGaming" in fname and "clean" not in fname:
            files.append((open(os.path.join(input_folder, fname), "rb"), fname))

    agg = EgamingAggregator(mcc_mnc_df)
    outputs = agg.process(files)

    for country, buf in outputs.items():
        out_path = f"Data_EGaming_{country}_clean.xlsx"
        with open(out_path, "wb") as f:
            f.write(buf.read())
        logger.info(f"Saved: {out_path}")
