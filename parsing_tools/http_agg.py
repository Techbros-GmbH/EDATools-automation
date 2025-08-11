from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import pandas as pd
from loguru import logger
from .parsing_config import HTTP_AGG_RULES, HTTP_DESIRED_ORDER, HTTP_MEAN_COLS


class HTTPAggregator:
    def __init__(self, mcc_mnc_df=None, test_case_df=None):
        """
        mcc_mnc_df: optional DataFrame with MCC, MNC, Operator
        test_case_df: optional DataFrame with HTTP_URL, Country, Test Name
        """
        self.mcc_mnc_df = mcc_mnc_df
        self.test_case_df = test_case_df

    def _load_file(self, file_obj, filename):
        """Load single Excel file into DataFrame."""
        df = pd.read_excel(file_obj)

        # Fill MCC/MNC
        df["MCC"] = pd.to_numeric(df["MCC"], errors="coerce")
        df["MNC"] = pd.to_numeric(df["MNC"], errors="coerce")
        first_mcc = df["MCC"].dropna().iloc[0] if not df["MCC"].dropna().empty else None
        first_mnc = df["MNC"].dropna().iloc[0] if not df["MNC"].dropna().empty else None
        df["MCC"].fillna(first_mcc, inplace=True)
        df["MNC"].fillna(first_mnc, inplace=True)

        # Extract Country
        base_name = filename.rsplit(".", 1)[0]
        parts = base_name.split("_")
        df["Country"] = parts[1] if len(parts) > 1 else "Unknown"

        # Type Mobility
        if "BMTT" in base_name:
            df["Type Mobility"] = "Test Train"
            logger.info(f"File {filename} identified as Test Train")
        elif "BMWT" in base_name:
            df["Type Mobility"] = "Walk Test"
            logger.info(f"File {filename} identified as Walk Test")
        elif "BMDT" in base_name:
            df["Type Mobility"] = "Drive Test"
            logger.info(f"File {filename} identified as Drive Test")
        else:
            df["Type Mobility"] = "Unknown"
            logger.warning(f"File {filename} has unknown Type Mobility")

        df["__source_file__"] = filename
        return df

    def _numeric_cast(self, df):
        for col in HTTP_MEAN_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def _qualifier(self, row):
        dns = row.get("DNS_Host_Name_Total_Resolution_Time_sec") or 0
        setup = row.get("HttpIpServiceSetupTime") or 0
        dl_tp = row.get("HTTP Download Throughput (kbps)")
        dl_avg = row.get("HTTP_Download_Average_Throughput")
        dl_dur = row.get("Seconds_Start_to_End_HTTP")
        ul_avg = row.get("HTTP_Upload_Average_Throughput")
        ul_dur = row.get("Seconds_Start_to_End_HTTP_Post")
        ip_intr = row.get("IP_Interruption_Time_ms")

        name = str(row.get("Test Name", "")).upper()
        if name in ["HTTP BROWSING LIVE", "HTTP BROSWING STATIC"]:
            if (
                (dns + setup) > 10
                or (dl_tp is None or dl_tp < 1000)
                or (dl_avg is not None and dl_avg < 1000)
            ):
                logger.info(
                    f"Test {name} not qualified due to DNS/setup or throughput issues"
                )
                return "Not Qualified"

        elif name == "HTTP FDFS DL":
            if (
                (dns + setup) > 10
                or (dl_avg is None or dl_avg < 1000)
                or (dl_dur is not None and dl_dur > 80000)
            ):
                logger.info(
                    f"Test {name} not qualified due to DNS/setup or download issues"
                )
                return "Not Qualified"
        elif name == "HTTP FDTT DL":
            if (
                (dns + setup) > 10
                or (dl_avg is not None and dl_avg < 1000)
                or (ip_intr is None or ip_intr > 2000)
            ):
                logger.info(
                    f"Test {name} not qualified due to DNS/setup or download issues"
                )
                return "Not Qualified"
        elif name == "HTTP FDFS UL":
            if (
                (dns + setup) > 10
                or (ul_avg is None or ul_avg < 500)
                or (ul_dur is not None and ul_dur > 40)
            ):
                logger.info(
                    f"Test {name} not qualified due to DNS/setup or upload issues"
                )
                return "Not Qualified"
        elif name == "HTTP FDTT UL":
            if (
                (dns + setup) > 10
                or (ul_avg is not None and ul_avg < 500)
                or (ip_intr is None or ip_intr > 2000)
            ):
                logger.info(
                    f"Test {name} not qualified due to DNS/setup or upload issues"
                )
                return "Not Qualified"
        return "Qualified"

    def process(self, files):
        """
        files: list of tuples [(file_obj, filename), ...]
        Returns: dict {country: BytesIO} of Excel files
        """
        # Step 1: Load all
        with ThreadPoolExecutor(max_workers=len(files)) as ex:
            df_list = list(ex.map(lambda f: self._load_file(*f), files))
        df = pd.concat(df_list, ignore_index=True)
        logger.info(f"Loaded {len(df)} rows from {len(files)} files")

        # Step 2: Forward-fill HTTP_URL
        segment = df["HttpServiceStatus"].notnull().cumsum()
        df["HTTP_URL"] = df["HTTP_URL"].ffill()
        df["HTTP_URL"] = df.groupby(segment)["HTTP_URL"].ffill()
        df.loc[
            df["HttpServiceStatus"].notnull() & df["HTTP_URL"].isnull(), "HTTP_URL"
        ] = df["HTTP_URL"].ffill()
        logger.info("Forward-filled HTTP_URL")

        # Step 3: Test Id
        is_new_test = (df["HTTP_URL"] != df["HTTP_URL"].shift(1)) & df[
            "HTTP_URL"
        ].notnull()
        df["Test Id"] = is_new_test.cumsum().where(df["HTTP_URL"].notnull())
        df["Test Id"] = df["Test Id"].apply(
            lambda x: f"Test {int(x)}" if pd.notnull(x) else None
        )
        logger.info("Assigned Test Ids")

        # Step 4: Cast numerics
        df = self._numeric_cast(df)
        logger.info("Casted numeric columns")

        # Step 5: Aggregate
        agg_df = (
            df.groupby(["HTTP_URL", "Test Id"], dropna=True)
            .agg(HTTP_AGG_RULES)
            .reset_index()
        )
        logger.info(f"Aggregated data to {len(agg_df)} rows")

        # Step 6: Map MCC/MNC
        if self.mcc_mnc_df is not None:
            agg_df = agg_df.merge(
                self.mcc_mnc_df[["MCC", "MNC", "Operator"]],
                on=["MCC", "MNC"],
                how="left",
            )
            agg_df["Operator"] = agg_df["Operator"].fillna("Unknown")
            logger.info("Mapped MCC/MNC to Operator")

        # Step 7: Map test case
        if self.test_case_df is not None:
            agg_df = agg_df.merge(
                self.test_case_df[["HTTP_URL", "Country", "Test Name"]],
                on=["HTTP_URL", "Country"],
                how="left",
            )
            agg_df["Test Name"] = agg_df["Test Name"].fillna("Not_found")
            logger.info("Mapped HTTP_URL to Test Name and Country")

        # Step 8: Qualifier
        logger.info("Applying qualifier to each row")
        agg_df["Qualifier"] = agg_df.apply(self._qualifier, axis=1)

        # Step 9: Calculated fields
        agg_df["Time to Transfer 1000 kB"] = agg_df[
            "HTTP Download Throughput (kbps)"
        ].apply(lambda x: round(1000 / x, 3) if pd.notnull(x) and x > 0 else "N/A")
        agg_df["Overall Session Time (s) DNS Request to first 1000kb"] = agg_df.apply(
            lambda row: round(
                (
                    row["DNS_Host_Name_Total_Resolution_Time_sec"]
                    + row["Time to Transfer 1000 kB"]
                ),
                3,
            )
            if pd.api.types.is_number(
                row.get("DNS_Host_Name_Total_Resolution_Time_sec")
            )
            and pd.api.types.is_number(row.get("Time to Transfer 1000 kB"))
            else "N/A",
            axis=1,
        )

        # Step 10: Reorder columns
        logger.info("Reordering columns")
        agg_df = agg_df[[col for col in HTTP_DESIRED_ORDER if col in agg_df.columns]]

        # Step 11: Export in-memory Excel per country
        logger.info("Exporting results to in-memory Excel files per country")
        output_files = {}
        for country, group_df in agg_df.groupby("Country"):
            buf = BytesIO()
            group_df.to_excel(buf, index=False)
            buf.seek(0)
            output_files[country] = buf
        return output_files


if __name__ == "__main__":
    # Example: load mapping files if you want them
    try:
        mcc_mnc_df = pd.read_excel("mncmcc_maping.xlsx")
    except FileNotFoundError:
        mcc_mnc_df = None

    try:
        test_case_df = pd.read_excel("test_case_map.xlsx")
    except FileNotFoundError:
        test_case_df = None

    # Create aggregator
    agg = HTTPAggregator(mcc_mnc_df, test_case_df)

    # Example: load Excel files from local folder for testing
    import os

    input_folder = "./input_http_files"
    files = []
    for fname in os.listdir(input_folder):
        if fname.endswith(".xlsx") and "HTTP" in fname and "clean" not in fname:
            files.append((open(os.path.join(input_folder, fname), "rb"), fname))

    # Run processing
    output_files = agg.process(files)

    # Save results individually
    for country, buf in output_files.items():
        out_name = f"HTTP_{country}_clean.xlsx"
        with open(out_name, "wb") as f:
            f.write(buf.read())
        print(f"✅ Saved {out_name}")
