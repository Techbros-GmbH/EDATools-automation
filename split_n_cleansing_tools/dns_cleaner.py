from __future__ import annotations

from io import BytesIO
from typing import Dict, Iterable, Tuple

import pandas as pd
from loguru import logger
from .split_n_cleansing_config import (
    DNS_RENAME_MAP,
    DNS_SCHEMA_GROUP,
    DNS_TEST_NAME_TO_GROUP,
    OPERATOR_CODES,
    TEST_NAME_CODES,
)
from .utils import (
    date_yyyymmdd,
    generate_test_ids,
    rename_columns,
    safe_columns,
    safe_name,
    safe_read_first_sheet,
    split_datetime,
)


class DNSPackager:
    """
    Transform raw DNS XLSX files into per–Test Name XLSX outputs.
    Uses configs imported above from parsing_config.

    process(files) -> Dict[str, BytesIO]
      files: Iterable[(file_obj, filename)]
    """

    def process(self, files: Iterable[Tuple[object, str]]) -> Dict[str, BytesIO]:
        # Load & stack
        df_list = []
        for fobj, fname in files:
            try:
                d = safe_read_first_sheet(fobj)
                d["SourceFile"] = str(fname).rsplit(".", 1)[0]
                df_list.append(d)
                logger.info(f"Loaded: {fname}")
            except Exception as e:
                logger.warning(f"Skip {fname}: {e}")

        if not df_list:
            raise ValueError("No DNS inputs loaded.")

        df = pd.concat(df_list, ignore_index=True)

        # Transform
        df = split_datetime(df)
        df = rename_columns(df, DNS_RENAME_MAP)
        df = generate_test_ids(df, TEST_NAME_CODES, OPERATOR_CODES)

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
            cols = safe_columns(block, wanted)

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
            date_str = date_yyyymmdd(first.get("Date"))
            country = safe_name(first.get("Route Name", "UnknownCountry"))
            test_str = safe_name(test_name)
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
        (
            open(
                "/Users/daffaarifadilah/techbros/fInal_parsing/Result/Parsing/DNS_Bremen_clean.xlsx",
                "rb",
            ),
            "DNS_Bremen_clean.xlsx",
        ),
    ]

    packager = DNSPackager()
    outputs = packager.process(files)

    # Save outputs to disk
    for name, buf in outputs.items():
        with open(name, "wb") as f:
            f.write(buf.getbuffer())
        logger.info(f"Saved: {name}")
