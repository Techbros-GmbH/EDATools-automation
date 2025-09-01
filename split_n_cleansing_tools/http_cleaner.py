from __future__ import annotations

import re
from io import BytesIO
from typing import Dict, Iterable, Tuple

import pandas as pd
from loguru import logger
from .split_n_cleansing_config import (
    HTTP_RENAME_MAP,
    HTTP_SCHEMA_GROUPS,
    HTTP_TEST_NAME_TO_GROUP,
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

class HttpPackager:
    """
    Transform raw HTTP XLSX files into per–Test Name XLSX outputs.

    process(files) -> Dict[str, BytesIO]
      files: Iterable[(file_obj, filename)]
    """
    # ---------- main API ----------
    def process(self, files: Iterable[Tuple[object, str]]) -> Dict[str, BytesIO]:
        """
        files: iterable of tuples (file_like_object, original_filename)
        returns: dict[output_filename -> BytesIO]
        """
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
            raise ValueError("No HTTP inputs loaded.")

        # 1) concat
        df = pd.concat(frames, ignore_index=True)

        # 2) transform
        df = split_datetime(df)
        df = rename_columns(df, HTTP_RENAME_MAP)
        df = generate_test_ids(df, TEST_NAME_CODES, OPERATOR_CODES)

        if "Test Name" not in df.columns:
            raise ValueError("'Test Name' column missing after rename.")

        outputs: Dict[str, BytesIO] = {}

        # 3) per Test Name export
        for test_name, test_block in df.groupby("Test Name"):
            group_key = HTTP_TEST_NAME_TO_GROUP.get(str(test_name))
            if not group_key:
                logger.info(f"Skip test '{test_name}': no schema group mapped.")
                continue

            wanted = list(HTTP_SCHEMA_GROUPS.get(group_key, [])) + ["Test_IDs"]
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
    from datetime import datetime
    from io import BytesIO
    from pathlib import Path

    input_dir = Path(
        "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/split/HTTPs/Input"
    )
    output_dir = Path(
        "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/split/HTTPs/Output2"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    files = [
        (BytesIO(p.read_bytes()), p.name) for p in sorted(input_dir.glob("*.xlsx"))
    ]
    if not files:
        raise SystemExit(f"No .xlsx found in {input_dir}")

    packager = HttpPackager()
    outputs = packager.process(files)

    log_path = output_dir / "log.txt"
    for name, buf in outputs.items():
        (output_dir / name).write_bytes(buf.getbuffer())
        msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ Saved: {name}"
        print(msg)
        with open(log_path, "a") as f:
            f.write(msg + "\n")

    print(f"Done. Wrote {len(outputs)} file(s) to {output_dir}")
