from __future__ import annotations

from io import BytesIO
from typing import Dict, Iterable, Tuple

import pandas as pd
from loguru import logger
from .split_n_cleansing_config import (
    OPERATOR_CODES,
    STREAMING_RENAME_MAP,
    STREAMING_SCHEMA_GROUPS,
    STREAMING_TEST_NAME_TO_GROUP,
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


class StreamingPackager:
    """
    Transform raw Streaming XLSX files into a single XLSX output (AllData sheet).
    Returns: Dict[filename -> BytesIO]
    """

    def __init__(self, default_group_key: str = "Streaming"):
        self.default_group_key = default_group_key

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
            raise ValueError("No Streaming inputs loaded.")

        # 1) concat
        df = pd.concat(frames, ignore_index=True)

        # 2) transform
        df = split_datetime(df)  # creates Date/Time from 'Date Time' then drops it

        # derived: normalize bearer if raw exists
        if (
            "StreamingServiceBearer" in df.columns
            and "Streaming Service Bearer" not in df.columns
        ):
            df["Streaming Service Bearer"] = df["StreamingServiceBearer"]

        # rename to canonical headers
        df = rename_columns(df, STREAMING_RENAME_MAP)

        # 3) Test_IDs
        df = generate_test_ids(df, TEST_NAME_CODES, OPERATOR_CODES)

        if df.empty:
            raise ValueError("No rows after preprocessing.")

        # 4) choose schema group from first row's Test Name (fallback to default)
        first = df.iloc[0]
        tname = str(first.get("Test Name", "") or "")
        group_key = STREAMING_TEST_NAME_TO_GROUP.get(tname, self.default_group_key)

        wanted = list(STREAMING_SCHEMA_GROUPS.get(group_key, [])) + ["Test_IDs"]
        cols = safe_columns(df, wanted)

        # Force Test_IDs to be 3rd column when present
        if "Test_IDs" in cols:
            cols.remove("Test_IDs")
            insert_at = 2 if len(cols) >= 2 else len(cols)
            cols.insert(insert_at, "Test_IDs")

        if not cols:
            raise ValueError(f"No columns from schema '{group_key}' exist in data.")

        out_df = df[cols]

        # 5) filename parts (single output file like your original script)
        date_str = date_yyyymmdd(first.get("Date"))
        country = safe_name(first.get("Route Name", "UnknownCountry"))
        out_name = f"{date_str}_{country}_BM_CDRData_Streaming.xlsx"

        # 6) write single file (AllData sheet)
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
            out_df.to_excel(writer, sheet_name="AllData", index=False)
        buf.seek(0)

        logger.info(f"Prepared: {out_name} (schema={group_key}, rows={len(out_df)})")
        return {out_name: buf}


if __name__ == "__main__":
    from datetime import datetime
    from pathlib import Path

    input_dir = Path(
        "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/split/Streaming/Input"
    )
    output_dir = Path(
        "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/split/Streaming/Output2"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    files = [(p.open("rb"), p.name) for p in sorted(input_dir.glob("*.xlsx"))]
    if not files:
        raise SystemExit(f"No .xlsx found in {input_dir}")

    packager = StreamingPackager()
    outputs = packager.process(files)

    log_path = output_dir / "log.txt"
    for name, buf in outputs.items():
        (output_dir / name).write_bytes(buf.getbuffer())
        msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ Saved: {name}"
        print(msg)
        with open(log_path, "a") as f:
            f.write(msg + "\n")

    print(f"Done. Wrote {len(outputs)} file(s) to {output_dir}")
