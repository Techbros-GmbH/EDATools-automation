import re
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import Iterable, Tuple

import pandas as pd
from loguru import logger

# pull these from your parsing_config (same style as Streaming)
from parsing_config import (
    VOICE_OTT_AGG_RULES,
    VOICE_OTT_DESIRED_ORDER,
    VOICE_OTT_MEAN_COLS,
)


class VoiceOTTAggregator:
    """
    Build clean Voice/OTT outputs per country (in-memory Excel files).

    Usage:
      files = [(open("Voice_OTT_AT_...xlsx","rb"), "Voice_OTT_AT_...xlsx"), ...]
      agg = VoiceOTTAggregator(mcc_mnc_df=..., test_case_df=None)
      outputs = agg.process(files)
      for country, buf in outputs.items():
          open(f"Voice_OTT_{country}_clean.xlsx","wb").write(buf.read())
    """

    def __init__(
        self,
        mcc_mnc_df: pd.DataFrame | None = None,
    ):
        self.mcc_mnc_df = mcc_mnc_df

    def _load_file(self, file_obj, filename: str) -> pd.DataFrame | None:
        try:
            df = pd.read_excel(file_obj)

            # MCC/MNC fill per file (keep your semantics)
            for k in ("MCC", "MNC"):
                if k in df.columns:
                    df[k] = pd.to_numeric(df[k], errors="coerce")
                    first = df[k].dropna().iloc[0] if not df[k].dropna().empty else None
                    df[k] = df[k].fillna(first)

            # Country from filename
            base = filename.rsplit(".", 1)[0]
            parts = base.split("_")
            df["Country"] = parts[1] if len(parts) > 1 else "Unknown"

            # Test Name from filename (same as your script)
            df["Test Name"] = (
                parts[2][-5:] + "_" + parts[3]
                if len(parts) > 3 and parts[2].endswith("Voice")
                else "Unknown"
            )

            # Side from IMSI pattern
            def extract_side(fname: str) -> str | None:
                m = re.search(r"IMSI[_\-]?\s*0*(\d+)", str(fname), flags=re.IGNORECASE)
                if not m:
                    return None
                n = m.group(1)
                return "Side A" if n == "1" else ("Side B" if n == "2" else f"IMSI{n}")

            df["Side"] = extract_side(base)

            # Type Mobility from filename
            if "BMTT" in base:
                df["Type Mobility"] = "Test Train"
            elif "BMWT" in base:
                df["Type Mobility"] = "Walk Test"
            elif "BMDT" in base:
                df["Type Mobility"] = "Drive Test"
            else:
                df["Type Mobility"] = "Unknown"

            df["__source_file__"] = filename
            logger.info(f"Loaded: {filename}")
            return df
        except Exception as e:
            logger.error(f"Failed to read {filename}: {e}")
            return None

    @staticmethod
    def _numeric_cast(df: pd.DataFrame) -> pd.DataFrame:
        for col in VOICE_OTT_MEAN_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    @staticmethod
    def _extract_sequence_from_voicelog(name: str | None) -> str | None:
        if not name:
            return None
        m = re.search(r"(OTT_\d+)", str(name))
        return m.group(1) if m else None

    # -------- segmentation (vectorized) --------
    @staticmethod
    def _fill_voicelog_and_assign_tests(df: pd.DataFrame) -> pd.DataFrame:
        """
        For each Side, create segments delimited by rows where DeviceDescription is not null.
        For each segment, take the last non-null VoiceLogfileName and assign it upward to the whole segment.
        Assign Test Id incrementally only for segments that have a non-null VoiceLogfileName.
        """
        if "Side" not in df.columns:
            df["Side"] = None

        df = df.copy()
        df["VoiceLogfileName_filled"] = pd.NA
        df["Test Id"] = pd.NA

        def per_side(sdf: pd.DataFrame) -> pd.DataFrame:
            # make sure original order is preserved
            sdf = sdf.sort_index()
            # segment id increases when DeviceDescription is present
            seg_id = sdf["DeviceDescription"].notnull().cumsum()
            sdf["_seg_id"] = seg_id

            # last non-null VoiceLogfileName per segment
            last_vl = sdf.groupby("_seg_id")["VoiceLogfileName"].agg(
                lambda x: x.dropna().iloc[-1] if x.dropna().size else pd.NA
            )
            sdf = sdf.join(last_vl.rename("_last_vl"), on="_seg_id")

            # assign filled name
            sdf["VoiceLogfileName_filled"] = sdf["_last_vl"]

            # enumerate only segments with a valid voice log
            segs_with_vl = last_vl[last_vl.notna()].index.tolist()
            seg_to_test = {seg: f"Test {i + 1}" for i, seg in enumerate(segs_with_vl)}
            sdf["Test Id"] = sdf["_seg_id"].map(seg_to_test)

            return sdf.drop(columns=["_seg_id", "_last_vl"])

        df = df.groupby("Side", group_keys=False).apply(per_side)
        return df

    # -------- MO/MT pairing & qualification --------
    @staticmethod
    def _apply_momt_qualification(
        agg_df: pd.DataFrame, time_window_seconds: int = 5
    ) -> pd.DataFrame:
        from datetime import timedelta

        df = agg_df.copy()
        df["Side_Group_Index"] = df.groupby("Side").cumcount()
        df["Pair_ID"] = None
        df["Qualifier"] = None

        # temp columns
        df["W"] = df.get("Call_Type")
        df["V"] = df.get("Call_Status")
        df["AK"] = pd.to_numeric(df.get("Call_Setup_Time_sec"), errors="coerce")
        df["AU"] = pd.to_numeric(df.get("Call Dropped VoLTE Count"), errors="coerce")
        df["CC"] = pd.to_numeric(df.get("SQ_MOS"), errors="coerce")
        df["Date Time"] = pd.to_datetime(df.get("Date Time"), errors="coerce")

        pair_id = 1
        used = set()
        delta = timedelta(seconds=time_window_seconds)

        for i, row in df.iterrows():
            if i in used or pd.isna(row["Date Time"]):
                continue

            side = row.get("Side")
            op = row.get("Operator")
            call_type = row.get("W")
            t = row["Date Time"]
            if call_type not in ("MO", "MT"):
                continue

            opp_side = "Side B" if side == "Side A" else "Side A"
            opp_type = "MT" if call_type == "MO" else "MO"

            candidates = df[
                (df["W"] == opp_type)
                & (df["Side"] == opp_side)
                & (df["Operator"] == op)
                & (df["Date Time"].notna())
                & (df["Date Time"].between(t - delta, t + delta))
                & (~df.index.isin(used))
            ]

            if not candidates.empty:
                j = candidates.index[0]

                def get_qual(r1, r2):
                    return (
                        "Not Qualified"
                        if (
                            pd.isna(r1.get("V"))
                            or r1.get("V") == "Failed"
                            or pd.isna(r1.get("AK"))
                            or r1.get("AK") > 15
                            or pd.isna(r1.get("AU"))
                            or r1.get("AU") == 1
                            or pd.isna(r1.get("CC"))
                            or r1.get("CC") < 2.7
                            or (
                                r1.get("CC") < 1.3
                                and pd.notna(r2.get("CC"))
                                and r2.get("CC") < 1.3
                            )
                        )
                        else "Qualified"
                    )

                df.at[i, "Qualifier"] = get_qual(row, df.loc[j])
                df.at[j, "Qualifier"] = get_qual(df.loc[j], row)
                df.at[i, "Pair_ID"] = pair_id
                df.at[j, "Pair_ID"] = pair_id
                used.update({i, j})
                pair_id += 1
            else:
                df.at[i, "Qualifier"] = "Incomplete"

        df.drop(columns=["W", "V", "AK", "AU", "CC"], inplace=True)
        return df

    # -------- main --------
    def process(self, files: Iterable[Tuple[object, str]]) -> dict[str, BytesIO]:
        # 1) load
        max_workers = max(1, min(8, len(list(files)) or 1))
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            df_list = list(ex.map(lambda f: self._load_file(*f), files))
        df_list = [d for d in df_list if d is not None]
        if not df_list:
            raise ValueError("No Voice_OTT raw files loaded.")
        df = pd.concat(df_list, ignore_index=True)

        # 2) segment/backfill + test id
        df = self._fill_voicelog_and_assign_tests(df)

        # 3) numeric cast
        df = self._numeric_cast(df)

        # 4) aggregate per (VoiceLogfileName_filled, Test Id)
        agg_rules = {k: v for k, v in VOICE_OTT_AGG_RULES.items() if k in df.columns}
        if not agg_rules:
            raise ValueError(
                "VOICE_OTT_AGG_RULES produced no usable keys for aggregation."
            )
        agg_df = (
            df.groupby(["VoiceLogfileName_filled", "Test Id"], dropna=True)
            .agg(agg_rules)
            .reset_index()
        )

        # 5) MCC/MNC -> Operator (defensive)
        if self.mcc_mnc_df is not None:
            try:
                map_df = self.mcc_mnc_df.copy()
                for k in ("MCC", "MNC"):
                    if k in map_df.columns:
                        map_df[k] = pd.to_numeric(map_df[k], errors="coerce").astype(
                            "Int64"
                        )
                for k in ("MCC", "MNC"):
                    if k in agg_df.columns:
                        agg_df[k] = pd.to_numeric(agg_df[k], errors="coerce").astype(
                            "Int64"
                        )
                if {"MCC", "MNC"}.issubset(map_df.columns) and {"MCC", "MNC"}.issubset(
                    agg_df.columns
                ):
                    agg_df = agg_df.merge(
                        map_df[["MCC", "MNC", "Operator"]],
                        on=["MCC", "MNC"],
                        how="left",
                    )
                    agg_df["Operator"] = agg_df["Operator"].fillna("Unknown")
                    logger.info("Operator mapping applied.")
            except Exception as e:
                logger.warning(f"Operator mapping failed: {e}")

        # 6) Sequence (Austria/Bremen)
        if "VoiceLogfileName_filled" in agg_df.columns:
            agg_df["Sequence"] = agg_df.apply(
                lambda r: self._extract_sequence_from_voicelog(
                    r.get("VoiceLogfileName_filled")
                )
                if r.get("Country") in ["Austria", "Bremen"]
                else None,
                axis=1,
            )

        # 7) MO/MT qualification
        agg_df = self._apply_momt_qualification(agg_df)

        # 8) finalize columns
        agg_df = agg_df.rename(columns={"VoiceLogfileName_filled": "VoiceLogfileName"})
        keep = [c for c in VOICE_OTT_DESIRED_ORDER if c in agg_df.columns]
        if not keep:
            raise ValueError(
                "VOICE_OTT_DESIRED_ORDER produced no existing columns to keep."
            )
        agg_df = agg_df[keep]

        # filter Qualified/Not Qualified only
        if "Qualifier" in agg_df.columns:
            agg_df = agg_df[agg_df["Qualifier"].isin(["Qualified", "Not Qualified"])]

        if "Country" not in agg_df.columns:
            raise ValueError("'Country' column is missing before exporting.")

        # 9) export per country to memory
        # sort by first kept column (prefer Date Time if present)
        sort_key = "Date Time" if "Date Time" in agg_df.columns else keep[0]
        agg_df = agg_df.sort_values(
            by=[col for col in ("Side", sort_key) if col in agg_df.columns]
        )

        outputs: dict[str, BytesIO] = {}
        for country, g in agg_df.groupby("Country"):
            buf = BytesIO()
            g.to_excel(buf, index=False)
            buf.seek(0)
            outputs[str(country).replace("/", "-").replace(" ", "_")] = buf
        return outputs


if __name__ == "__main__":
    import os

    logger.add("voice_ott_aggregator.log", rotation="1 MB")

    # Optional mappings
    try:
        mcc_mnc_df = pd.read_excel("mncmcc_maping.xlsx")
    except FileNotFoundError:
        mcc_mnc_df = None

    # Collect demo inputs
    input_folder = "./input_voice_ott_files"
    files: list[Tuple[object, str]] = []
    if os.path.isdir(input_folder):
        for fname in os.listdir(input_folder):
            if (
                fname.endswith(".xlsx")
                and "Voice_OTT" in fname
                and "clean" not in fname
            ):
                files.append((open(os.path.join(input_folder, fname), "rb"), fname))
    else:
        logger.warning(f"Folder not found: {input_folder}")

    if not files:
        logger.error("No input files found for demo run.")
    else:
        agg = VoiceOTTAggregator(mcc_mnc_df=mcc_mnc_df)
        outputs = agg.process(files)
        for country, buf in outputs.items():
            out_path = f"Voice_OTT_{country}_clean.xlsx"
            with open(out_path, "wb") as f:
                f.write(buf.read())
            logger.info(f"Saved: {out_path}")
