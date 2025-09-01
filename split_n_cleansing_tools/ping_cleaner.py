from __future__ import annotations

from io import BytesIO
from typing import Dict, Iterable, Tuple

import pandas as pd
from pathlib import Path
from loguru import logger

from .split_n_cleansing_config import (
    PING_RENAME_MAP,
    PING_SCHEMA_GROUPS,
    PING_TEST_NAME_TO_GROUP,
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


class PingPackager:
    """
    Transform raw Ping XLSX files into per–Test Name XLSX outputs.

    process(files) -> Dict[str, BytesIO]
      files: Iterable[(file_obj, filename)]
    """

    # ---------- main API ----------
    def process(self, files: Iterable[Tuple[object, str]]) -> Dict[str, BytesIO]:
        frames = []
        for fobj, fname in files:
            try:
                d = safe_read_first_sheet(fobj)
                d["SourceFile"] = str(fname).rsplit(".", 1)[0]
                frames.append(d)
                logger.info(f"Loaded: {fname}")
            except Exception as e:
                logger.warning(f"Skip {fname}: {e}")

        if not frames:
            raise ValueError("No Ping inputs loaded.")

        # 1) concat
        df = pd.concat(frames, ignore_index=True)

        # 2) transform
        df = split_datetime(df)  # makes Date/Time from 'Date Time' and drops it

        # Optional derived: normalize data radio bearer (if raw key exists)
        if "PingDataRadioBearer" in df.columns and "Ping Data Radio Bearer" not in df.columns:
            df["Ping Data Radio Bearer"] = df["PingDataRadioBearer"]

        # rename to canonical headers
        df = rename_columns(df, PING_RENAME_MAP)

        # Guard: sometimes inputs contain duplicate “Operator”/“Test Name” columns
        # df = self._collapse_dupe_key_columns(df, keys=("Test Name", "Operator"))

        # IDs
        df = generate_test_ids(df, TEST_NAME_CODES, OPERATOR_CODES)

        if "Test Name" not in df.columns:
            raise ValueError("'Test Name' column missing after rename.")

        outputs: Dict[str, BytesIO] = {}

        # 3) per Test Name export
        for test_name, test_block in df.groupby("Test Name"):
            group_key = PING_TEST_NAME_TO_GROUP.get(str(test_name))
            if not group_key:
                logger.info(f"Skip test '{test_name}': no schema group mapped.")
                continue

            wanted = list(PING_SCHEMA_GROUPS.get(group_key, [])) + ["Test_IDs"]
            cols = safe_columns(test_block, wanted)

            # Force Test_IDs to be 3rd column when present
            if "Test_IDs" in cols:
                cols.remove("Test_IDs")
                insert_at = 2 if len(cols) >= 2 else len(cols)
                cols.insert(insert_at, "Test_IDs")

            if not cols:
                logger.info(
                    f"Skip test '{test_name}': no columns from schema exist in data."
                )
                continue

            out_df = test_block[cols]

            first = test_block.iloc[0]
            date_str = date_yyyymmdd(first.get("Date"))
            country = safe_name(first.get("Route Name", "UnknownCountry"))
            test_str = safe_name(test_name)
            out_name = f"{date_str}_{country}_BM_CDRData_{test_str}.xlsx"

            buf = BytesIO()
            with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
                out_df.to_excel(writer, sheet_name="AllData", index=False)
            buf.seek(0)

            outputs[out_name] = buf
            logger.info(f"Prepared: {out_name} (schema={group_key})")

        return outputs

if __name__ == "__main__":
    # Folder-based runner to mimic your original script behavior
    input_folder = Path("/Users/daffaarifadilah/techbros/fInal_parsing/Result/Parsing/new_ping")
    output_folder = Path("/Users/daffaarifadilah/techbros/fInal_parsing/Result/Parsing/new_ping/output")
    output_folder.mkdir(parents=True, exist_ok=True)

    files = []
    for file_path in input_folder.glob("*.xlsx"):
        try:
            files.append((open(file_path, "rb"), file_path.name))
        except Exception as e:
            logger.warning(f"Could not open {file_path.name}: {e}")

    if not files:
        logger.error("No input files found.")
    else:
        packager = PingPackager()
        outputs = packager.process(files)

        for name, buf in outputs.items():
            out_path = output_folder / name
            with open(out_path, "wb") as f:
                f.write(buf.getbuffer())
            logger.success(f"✅ Saved: {out_path}")
