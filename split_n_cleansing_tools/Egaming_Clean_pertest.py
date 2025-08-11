from __future__ import annotations

import re
from io import BytesIO
from typing import Dict, Iterable, Tuple

import pandas as pd
from loguru import logger

from split_n_cleansing_config import (
    EGAMING_RENAME_MAP,
    EGAMING_SCHEMA_GROUPS,
    EGAMING_TEST_NAME_TO_GROUP,
    OPERATOR_CODES,
    TEST_NAME_CODES,
)


class EgamingPackager:
    """
    Transform raw E_gaming XLSX files into per–Test Name XLSX outputs.
    Uses configs imported above from parsing_config.

    process(files) -> Dict[str, BytesIO]
      files: Iterable[(file_obj, filename)]
    """

    # ---------- helpers ----------

    @staticmethod
    def _safe_read_first_sheet(file_obj) -> pd.DataFrame:
        xls = pd.ExcelFile(file_obj)
        return xls.parse(xls.sheet_names[0])

    @staticmethod
    def _split_datetime(df: pd.DataFrame) -> pd.DataFrame:
        # Split "Date Time" -> Date, Time if needed
        if "Date Time" in df.columns and not {"Date", "Time"}.issubset(df.columns):
            parts = df["Date Time"].astype(str).str.split(" ", n=1, expand=True)
            if parts.shape[1] == 2:
                parts.columns = ["Date", "Time"]
                df = pd.concat([df.drop(columns=["Date Time"]), parts], axis=1)
        return df

    @staticmethod
    def _safe_name(val: object) -> str:
        return (
            re.sub(r'[/\\:*?"<>| ]+', "_", ("" if val is None else str(val)).strip())
            or "Unknown"
        )

    @staticmethod
    def _date_yyyymmdd(val) -> str:
        ts = pd.to_datetime(val, errors="coerce")
        return ts.strftime("%Y%m%d") if pd.notna(ts) else "UnknownDate"

    @staticmethod
    def _safe_columns(df: pd.DataFrame, wanted: list[str]) -> list[str]:
        # keep only columns that exist, preserving order
        seen = set()
        cols = [c for c in wanted if c in df.columns and not (c in seen or seen.add(c))]
        return cols

    @staticmethod
    def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:
        usable = {k: v for k, v in EGAMING_RENAME_MAP.items() if k in df.columns}
        return df.rename(columns=usable)

    @staticmethod
    def _generate_test_ids(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["Test_IDs"] = None
        if not {"Test Name", "Operator"}.issubset(df.columns):
            return df

        for (tname, oper), grp in df.groupby(["Test Name", "Operator"], dropna=False):
            tcode = TEST_NAME_CODES.get(str(tname), 0)
            ocode = OPERATOR_CODES.get(str(oper), 0)
            for n, idx in enumerate(grp.index, start=1):
                df.at[idx, "Test_IDs"] = f"{tcode}{ocode}{n:04d}"
        return df

    # ---------- main ----------

    def process(self, files: Iterable[Tuple[object, str]]) -> Dict[str, BytesIO]:
        # 1) Load all inputs (first sheet) and stack
        frames = []
        for fobj, fname in files:
            try:
                d = self._safe_read_first_sheet(fobj)
                d["SourceFile"] = str(fname).rsplit(".", 1)[0]
                frames.append(d)
                logger.info(f"Loaded: {fname}")
            except Exception as e:
                logger.warning(f"Skip {fname}: {e}")

        if not frames:
            raise ValueError("No E_gaming inputs loaded.")

        df = pd.concat(frames, ignore_index=True)

        # 2) Transform
        df = self._split_datetime(df)
        df = self._rename_columns(df)
        df = self._generate_test_ids(df)

        if "Test Name" not in df.columns:
            raise ValueError("'Test Name' column missing after rename.")

        outputs: Dict[str, BytesIO] = {}

        # 3) Export per Test Name
        for test_name, test_block in df.groupby("Test Name"):
            group_key = EGAMING_TEST_NAME_TO_GROUP.get(str(test_name))
            if not group_key:
                logger.info(f"Skip test '{test_name}': no schema group mapped.")
                continue

            wanted = list(EGAMING_SCHEMA_GROUPS.get(group_key, [])) + ["Test_IDs"]
            cols = self._safe_columns(test_block, wanted)

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

            # 4) Build output filename
            first = test_block.iloc[0]
            date_str = self._date_yyyymmdd(first.get("Date"))
            country = self._safe_name(first.get("Route Name", "UnknownCountry"))
            test_str = self._safe_name(test_name)
            out_name = f"{date_str}_{country}_BM_CDRData_{test_str}.xlsx"

            # 5) Write to memory
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
                out_df.to_excel(writer, sheet_name="AllData", index=False)
            buf.seek(0)
            outputs[out_name] = buf
            logger.info(f"Prepared: {out_name} (schema={group_key})")

        return outputs


# ---------- optional: run & save when executed directly ----------
if __name__ == "__main__":
    from io import BytesIO
    from pathlib import Path

    input_dir = Path(
        "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/split/E_gaming/Input"
    )
    output_dir = Path(
        "/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/split/E_gaming/Output2"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    files = [
        (BytesIO(p.read_bytes()), p.name) for p in sorted(input_dir.glob("*.xlsx"))
    ]
    if not files:
        raise SystemExit(f"No .xlsx found in {input_dir}")

    packager = EgamingPackager()
    outputs = packager.process(files)

    for name, buf in outputs.items():
        (output_dir / name).write_bytes(buf.getbuffer())
        print(f"✅ Saved: {output_dir / name}")

    print(f"Done. Wrote {len(outputs)} file(s) to {output_dir}")
