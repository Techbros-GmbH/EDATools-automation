from __future__ import annotations
from pathlib import Path
from typing import Iterable, Tuple, Dict
from io import BytesIO

import pandas as pd
from loguru import logger


class ExcelMerger:
    """
    Merge multiple Excel files into one DataFrame / Excel file.
    """

    def __init__(self, output_name: str = "merged_output.xlsx"):
        self.output_name = output_name

    def process(self, files: Iterable[Tuple[object, str]]) -> Dict[str, BytesIO]:
        """
        Merge all input Excel files into a single output.

        Parameters
        ----------
        files : iterable of (file_like_object, filename)

        Returns
        -------
        dict[str, BytesIO] : {output_filename: excel_bytes}
        """
        merged_df = pd.DataFrame()

        for fobj, fname in files:
            try:
                df = pd.read_excel(fobj)
                df.columns = df.columns.str.strip()  # normalize headers
                merged_df = pd.concat([merged_df, df], ignore_index=True, sort=False)
                logger.info(f"✅ Merged: {fname}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to read {fname}: {e}")

        if merged_df.empty:
            raise ValueError("No valid Excel data loaded.")

        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            merged_df.to_excel(writer, index=False)
        buf.seek(0)

        return {self.output_name: buf}


if __name__ == "__main__":
    # Example usage
    input_folder = Path("/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/Bremen Output/merge/Merge_clean/Data")
    output_folder = Path("/mnt/c/Users/User/Documents/Indra/geo/CDR/parsing/Bremen Output/merge")
    output_folder.mkdir(parents=True, exist_ok=True)

    files = []
    for file_path in sorted(input_folder.glob("*.xlsx")):
        try:
            files.append((open(file_path, "rb"), file_path.name))
        except Exception as e:
            logger.warning(f"❌ Could not open file {file_path.name}: {e}")

    if not files:
        logger.error("No Excel files found in input folder.")
    else:
        merger = ExcelMerger("merged_output.xlsx")
        outputs = merger.process(files)

        for name, buf in outputs.items():
            out_path = output_folder / name
            with open(out_path, "wb") as f:
                f.write(buf.getbuffer())
            logger.success(f"🎉 Saved merged file: {out_path}")
