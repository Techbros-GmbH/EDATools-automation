from __future__ import annotations

import re
from io import BytesIO
from typing import Dict, Iterable, Tuple

import pandas as pd
from loguru import logger

from split_n_cleansing_config import (
    OPERATOR_CODES,
    DNS_RENAME_MAP,
    DNS_SCHEMA_GROUP,
    TEST_NAME_CODES,
    DNS_TEST_NAME_TO_GROUP,
)


class DNSPackager:
    """
    Transform raw DNS XLSX files into per–Test Name XLSX outputs.
    Uses configs imported above from parsing_config.

    process(files) -> Dict[str, BytesIO]
      files: Iterable[(file_obj, filename)]
    """
    @staticmethod
    def _safe_read_first_sheet(file_obj) -> pd.DataFrame:
        xls = pd.ExcelFile(file_obj)
        return xls.parse(xls.sheet_names[0])

    @staticmethod
    def _split_datetime(df: pd.DataFrame) -> pd.DataFrame:
        if "Date Time" in df.columns and not {"Date", "Time"}.issubset(df.columns):
            parts = df["Date Time"].astype(str).str.split(" ", n=1, expand=True)
            if parts.shape[1] == 2:
                parts.columns = ["Date", "Time"]
                df = pd.concat([df.drop(columns=["Date Time"]), parts], axis=1)
        return df

    @staticmethod
    def _safe_columns(df: pd.DataFrame, wanted: list[str]) -> list[str]:
        return [c for c in wanted if c in df.columns]

    @staticmethod
    def _safe_name(s: object) -> str:
        return (
            re.sub(r'[/\\:*?"<>| ]+', "_", str(s).strip() if s is not None else "")
            or "Unknown"
        )

    @staticmethod
    def _date_yyyymmdd(val) -> str:
        ts = pd.to_datetime(val, errors="coerce")
        return ts.strftime("%Y%m%d") if pd.notna(ts) else "UnknownDate"

    @staticmethod
    def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:
        usable = {k: v for k, v in DNS_RENAME_MAP.items() if k in df.columns}
        return df.rename(columns=usable)

    @staticmethod
    def _generate_test_ids(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["Test_IDs"] = None
        if not {"Test Name", "Operator"}.issubset(df.columns):
            return df

        for (tname, oper), g in df.groupby(["Test Name", "Operator"], dropna=False):
            tcode = TEST_NAME_CODES.get(str(tname), 0)
            ocode = OPERATOR_CODES.get(str(oper), 0)
            for n, idx in enumerate(g.index, start=1):
                df.at[idx, "Test_IDs"] = f"{tcode}{ocode}{n:04d}"
        return df

    # ---------- main API ----------

    def process(self, files: Iterable[Tuple[object, str]]) -> Dict[str, BytesIO]:
        # Load & stack
        df_list = []
        for fobj, fname in files:
            try:
                d = self._safe_read_first_sheet(fobj)
                d["SourceFile"] = str(fname).rsplit(".", 1)[0]
                df_list.append(d)
                logger.info(f"Loaded: {fname}")
            except Exception as e:
                logger.warning(f"Skip {fname}: {e}")

        if not df_list:
            raise ValueError("No DNS inputs loaded.")

        df = pd.concat(df_list, ignore_index=True)

        # Transform
        df = self._split_datetime(df)
        df = self._rename_columns(df)
        df = self._generate_test_ids(df)

        if "Test Name" not in df.columns:
            raise ValueError("'Test Name' column missing after rename.")

        outputs: Dict[str, BytesIO] = {}

        # Per-test export
        for test_name, block in df.groupby("Test Name"):
            group_key = DNS_TEST_NAME_TO_GROUP.get(str(test_name))
            if not group_key:
                logger.info(f"Skip test '{test_name}': no schema group mapped.")
                continue

            wanted = list(DNS_SCHEMA_GROUP.get(group_key, [])) + ["Test_IDs"]
            cols = self._safe_columns(block, wanted)

            # Force Test_IDs to 3rd position if present
            if "Test_IDs" in cols:
                cols.remove("Test_IDs")
                cols.insert(min(2, len(cols)), "Test_IDs")

            if not cols:
                logger.info(
                    f"Skip test '{test_name}': no columns from schema exist in data."
                )
                continue

            out_df = block[cols]

            # Filename
            first = block.iloc[0]
            date_str = self._date_yyyymmdd(first.get("Date"))
            country = self._safe_name(first.get("Route Name", "UnknownCountry"))
            test_str = self._safe_name(test_name)
            out_name = f"{date_str}_{country}_BM_CDRData_{test_str}.xlsx"

            # Write to memory
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
                out_df.to_excel(w, sheet_name="AllData", index=False)
            buf.seek(0)
            outputs[out_name] = buf

        return outputs


if __name__ == "__main__":
    import os

    # Example input files
    # input_folder = (
    #     "/Users/daffaarifadilah/techbros/fInal_parsing/Result/Parsing"
    # )
    # files = []
    # if input_folder:
    #     for fname in os.listdir(input_folder):
    #         if fname.endswith(".xlsx") and "DNS" in fname and "clean" not in fname:
    #             files.append((open(os.path.join(input_folder, fname), "rb"), fname))
    # else:
    files = [
        (open("/Users/daffaarifadilah/techbros/fInal_parsing/Result/Parsing/DNS_Bremen_clean.xlsx", "rb"), "DNS_Bremen_clean.xlsx"),
    ]

    packager = DNSPackager()
    outputs = packager.process(files)

    # Save outputs to disk
    for name, buf in outputs.items():
        with open(name, "wb") as f:
            f.write(buf.getbuffer())
        logger.info(f"Saved: {name}")
