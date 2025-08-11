import re
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import pandas as pd
from loguru import logger
from .parsing_config import DNS_AGG_RULES, DNS_DESIRED_ORDER, DNS_MEAN_COLS


class DNSAggregator:
    def __init__(self, mcc_mnc_df=None, test_case_df=None):
        self.mcc_mnc_df = mcc_mnc_df
        self.test_case_df = test_case_df

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

            # Country
            base_name = filename.rsplit(".", 1)[0]
            parts = base_name.split("_")
            df["Country"] = parts[1] if len(parts) > 1 else "Unknown"

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
        for col in DNS_MEAN_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def process(self, files):
        # Load all
        with ThreadPoolExecutor(max_workers=4) as ex:
            df_list = list(ex.map(lambda f: self._load_file(*f), files))
        df_list = [d for d in df_list if d is not None]
        if not df_list:
            raise ValueError("No DNS raw files loaded.")

        df = pd.concat(df_list, ignore_index=True)

        # Forward fill
        segment = df["HttpServiceStatus"].notnull().cumsum()
        df["HTTP_URL"] = df["HTTP_URL"].ffill()
        df["HTTP_URL"] = df.groupby(segment)["HTTP_URL"].ffill()
        df.loc[
            df["HttpServiceStatus"].notnull() & df["HTTP_URL"].isnull(), "HTTP_URL"
        ] = df["HTTP_URL"].ffill()

        # Test Id
        is_new_test = (df["HTTP_URL"] != df["HTTP_URL"].shift(1)) & df[
            "HTTP_URL"
        ].notnull()
        df["Test Id"] = is_new_test.cumsum().where(df["HTTP_URL"].notnull())
        df["Test Id"] = df["Test Id"].apply(
            lambda x: f"Test {int(x)}" if pd.notnull(x) else None
        )

        # Numeric
        df = self._numeric_cast(df)

        # Aggregate
        agg_df = (
            df.groupby(["HTTP_URL", "Test Id"], dropna=True)
            .agg(DNS_AGG_RULES)
            .reset_index()
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
                logger.error(f"MCC/MNC mapping failed: {e}")

        # Test case mapping
        if self.test_case_df is not None:
            try:
                agg_df = agg_df.merge(
                    self.test_case_df[["HTTP_URL", "Country", "Test Name"]],
                    on=["HTTP_URL", "Country"],
                    how="left",
                )
                agg_df["Test_Name_1"] = agg_df["Test Name"].fillna("Not_found")
                agg_df["Test_Name_2"] = "DNS"
            except Exception as e:
                logger.error(f"Test case mapping failed: {e}")
        else:
            agg_df["Test_Name_1"] = "Not_found"
            agg_df["Test_Name_2"] = "DNS"

        # Sequence
        agg_df["Sequence"] = agg_df.apply(
            lambda row: re.search(
                r"EQ1_Data_(TRP\d+_\d+)_MS\d+", str(row["HttpLogfileName"])
            ).group(1)
            if row.get("Country") in ["Austria", "Bremen"]
            and re.search(r"EQ1_Data_(TRP\d+_\d+)_MS\d+", str(row["HttpLogfileName"]))
            else None,
            axis=1,
        )

        # Reorder
        agg_df = agg_df[[col for col in DNS_DESIRED_ORDER if col in agg_df.columns]]

        # Export per country to memory
        output_files = {}
        for country, group_df in agg_df.groupby("Country"):
            buf = BytesIO()
            group_df.to_excel(buf, index=False)
            buf.seek(0)
            output_files[country] = buf

        return output_files


if __name__ == "__main__":
    import os

    # Example mapping files
    try:
        mcc_mnc_df = pd.read_excel("mncmcc_maping.xlsx")
    except FileNotFoundError:
        mcc_mnc_df = None

    try:
        test_case_df = pd.read_excel("test_case_map.xlsx")
    except FileNotFoundError:
        test_case_df = None

    # Example input folder
    input_folder = "./input_dns_files"
    files = []
    for fname in os.listdir(input_folder):
        if fname.endswith(".xlsx") and "HTTP" in fname and "clean" not in fname:
            files.append((open(os.path.join(input_folder, fname), "rb"), fname))

    agg = DNSAggregator(mcc_mnc_df, test_case_df)
    outputs = agg.process(files)

    # Save each output
    for country, buf in outputs.items():
        out_path = f"DNS_{country}_clean.xlsx"
        with open(out_path, "wb") as f:
            f.write(buf.read())
        logger.info(f"Saved: {out_path}")
