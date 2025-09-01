import asyncio
import inspect
import os
import sys
import zipfile
from concurrent.futures import ProcessPoolExecutor
from configparser import ConfigParser
from io import BytesIO
from typing import Dict, List, Tuple, Union

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

path_this = os.path.dirname(os.path.abspath(__file__))
path_project = os.path.dirname(os.path.join(path_this, ".."))
path_root = os.path.dirname(os.path.join(path_this, "../.."))
sys.path.append(path_root)
sys.path.append(path_project)
sys.path.append(path_this)

import kqix
import parsing_tools as parsing
import split_n_cleansing_tools as cleaner
from merge_testcase import ExcelMerger

app = FastAPI(
    title="Techbros EDA Tools Automation API",
    description="API for automating EDA tools data aggregation and processing.",
    version="1.0.0",
)
config = ConfigParser()
config.read(os.path.join(path_root, "config.ini"))
MCC_MNC_PATH = os.path.join(path_root, config.get("default", "mcc_mnc_path"))
TEST_CASE_PATH = os.path.join(path_root, config.get("default", "test_case_path"))

_NAME_MAP = {
    "dns": ["DNSAggregator", "DNSPackager"],
    "http": ["HTTPAggregator", "HttpPackager"],
    "egaming": ["EgamingAggregator", "EgamingPackager"],
    "ping": ["PingAggregator", "PingPackager"],
    "streaming": ["StreamingAggregator", "StreamingPackager"],
    "video_chat": ["VideoChatAggregator", "VideoChatPackager"],
    "videochat": ["VideoChatAggregator", "VideoChatPackager"],
    "voice_m2m": ["VoiceM2MAggregator", "VoiceM2MPackager"],
    "voice_ott": ["VoiceOTTAggregator", "VoiceOTTPackager"],
    "mos_m2m": ["MOSM2MAggregator", "MOSM2MPackager"],
    "mos_ott": ["MOSOTTAggregator", "MOSOTTPackager"],
}

_KQI_FACTORY = {
    "http": lambda: kqix.HttpKQISummarizer(),
    "streaming": lambda: kqix.StreamingKQISummarizer(),
    "ping": lambda: kqix.PingKQISummarizer(),
    "egaming": lambda: kqix.EgamingKQISummarizer(),
    "dns": lambda: kqix.DNSKQISummarizer(),
    "videochat": lambda: kqix.VideoChatKQISummarizer(),
    "video_chat": lambda: kqix.VideoChatKQISummarizer(),
    "mos_m2m": lambda: kqix.MOSKQISummarizer("m2m"),
    "mos_ott": lambda: kqix.MOSKQISummarizer("ott"),
    "voice_m2m": lambda: kqix.VoiceKQISummarizer("m2m"),
    "voice_ott": lambda: kqix.VoiceKQISummarizer("ott"),
}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def make_kqi(filename: str) -> str | None:
    name = (filename or "").lower()
    for key in _KQI_FACTORY.keys():
        if key in name:
            return key
    return None


def make_aggregator(kind: str, *, mcc_mnc_df=None, test_case_df=None):
    kind = (kind or "").lower()

    mcc_mnc_df = pd.read_excel(MCC_MNC_PATH) if mcc_mnc_df is None else mcc_mnc_df
    test_case_df = (
        pd.read_excel(TEST_CASE_PATH) if test_case_df is None else test_case_df
    )

    try:
        cls_names = _NAME_MAP[kind]  # FIX: use kind, not kind[0]
        cls_name = cls_names[0]  # Aggregator class name
        cls = getattr(parsing, cls_name)
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Unknown type_test: {kind}")

    return cls(mcc_mnc_df=mcc_mnc_df, test_case_df=test_case_df)


def make_packager(kind: str):
    """Return the packager class instance from `split_n_cleansing_tools`."""
    kind = (kind or "").lower()
    try:
        cls_names = _NAME_MAP[kind]
        cls_name = cls_names[1]
        cls = getattr(cleaner, cls_name)
    except KeyError:
        raise HTTPException(
            status_code=400, detail=f"Unknown type_test for packager: {kind}"
        )
    # Most packagers don't need extra ctor args
    return cls()


# --- NEW WORKER: AGGREGATOR -> PACKAGER PIPELINE ---


def _run_split_n_cleansing(
    type_test: str,
    file_specs: List[Tuple[bytes, str]],
) -> Tuple[str, Dict[str, bytes]]:
    """
    Pipeline worker:
      1) Run aggregator (parsing_tools)
      2) Feed aggregator outputs into packager (split_n_cleansing_tools)
      3) Return dict[final_filename -> bytes]
    """
    # Rebuild BytesIO for aggregator
    rebuilt_specs: List[Tuple[BytesIO, str]] = [
        (BytesIO(b), fn) for (b, fn) in file_specs
    ]

    # 1) Aggregate
    agg = make_aggregator(type_test)
    agg_outputs = agg.process(rebuilt_specs)

    # --- Normalize aggregator outputs to dict[str, bytes] ---
    norm: Dict[str, bytes] = {}
    if isinstance(agg_outputs, dict):
        for name, obj in agg_outputs.items():
            if isinstance(obj, bytes):
                norm[name] = obj
            elif isinstance(obj, BytesIO):
                norm[name] = obj.getvalue()
            elif isinstance(obj, pd.DataFrame):
                norm[name] = _df_to_excel_bytes(obj)
            else:
                # Best-effort: try file-like
                try:
                    norm[name] = obj.getvalue()
                except Exception:
                    norm[name] = _df_to_excel_bytes(pd.DataFrame(obj))
    else:
        # Single output cases
        if isinstance(agg_outputs, bytes):
            norm["output.xlsx"] = agg_outputs
        elif isinstance(agg_outputs, BytesIO):
            norm["output.xlsx"] = agg_outputs.getvalue()
        elif isinstance(agg_outputs, pd.DataFrame):
            norm["output.xlsx"] = _df_to_excel_bytes(agg_outputs)
        else:
            try:
                norm["output.xlsx"] = agg_outputs.getvalue()
            except Exception:
                norm["output.xlsx"] = _df_to_excel_bytes(pd.DataFrame(agg_outputs))

    # 2) Run packager: convert normalized bytes into BytesIO for packager input
    pkg = make_packager(type_test)
    pkg_inputs: List[Tuple[BytesIO, str]] = [
        (BytesIO(b), name) for name, b in norm.items()
    ]

    pkg_outputs = pkg.process(pkg_inputs)

    # 3) Normalize packager outputs to dict[str, bytes]
    out: Dict[str, bytes] = {}
    if isinstance(pkg_outputs, dict):
        for final_name, obj in pkg_outputs.items():
            if isinstance(obj, bytes):
                out[final_name] = obj
            elif isinstance(obj, BytesIO):
                out[final_name] = obj.getvalue()
            elif isinstance(obj, pd.DataFrame):
                out[final_name] = _df_to_excel_bytes(obj)
            else:
                try:
                    out[final_name] = obj.getvalue()
                except Exception:
                    out[final_name] = _df_to_excel_bytes(pd.DataFrame(obj))
    else:
        # Single output fallback
        final_name = f"{type_test.upper()}_clean.xlsx"
        if isinstance(pkg_outputs, bytes):
            out[final_name] = pkg_outputs
        elif isinstance(pkg_outputs, BytesIO):
            out[final_name] = pkg_outputs.getvalue()
        elif isinstance(pkg_outputs, pd.DataFrame):
            out[final_name] = _df_to_excel_bytes(pkg_outputs)
        else:
            try:
                out[final_name] = pkg_outputs.getvalue()
            except Exception:
                out[final_name] = _df_to_excel_bytes(pd.DataFrame(pkg_outputs))

    return type_test, out


def _run_excel_merger(
    file_specs: List[Tuple[bytes, str]],
    output_name: str = "merged_output.xlsx",
) -> Dict[str, bytes]:
    """
    Run ExcelMerger on uploaded file bytes.
    Returns {filename -> bytes} (usually one file).
    """
    rebuilt: List[Tuple[BytesIO, str]] = [(BytesIO(b), fn) for (b, fn) in file_specs]

    merger = ExcelMerger(output_name=output_name)
    outputs = merger.process(rebuilt)  # expected: {output_name: BytesIO}

    out: Dict[str, bytes] = {}
    if isinstance(outputs, dict):
        for name, obj in outputs.items():
            if isinstance(obj, bytes):
                out[name] = obj
            elif isinstance(obj, BytesIO):
                out[name] = obj.getvalue()
            elif isinstance(obj, pd.DataFrame):
                out[name] = _df_to_excel_bytes(obj)
            else:
                try:
                    out[name] = obj.getvalue()
                except Exception:
                    out[name] = _df_to_excel_bytes(pd.DataFrame(obj))
    else:
        # Fallback: single output scenario
        name = output_name or "merged_output.xlsx"
        if isinstance(outputs, bytes):
            out[name] = outputs
        elif isinstance(outputs, BytesIO):
            out[name] = outputs.getvalue()
        elif isinstance(outputs, pd.DataFrame):
            out[name] = _df_to_excel_bytes(outputs)
        else:
            try:
                out[name] = outputs.getvalue()
            except Exception:
                out[name] = _df_to_excel_bytes(pd.DataFrame(outputs))

    return out


def _run_packager_only(
    type_test: str,
    file_specs: List[Tuple[bytes, str]],
) -> Tuple[str, Dict[str, bytes]]:
    """
    Run only the packager for a given type_test.

    Parameters
    ----------
    type_test : e.g., 'dns', 'http', ...
    file_specs : List of (file_bytes, filename)

    Returns
    -------
    (type_test, {output_filename -> excel_bytes})
    """
    # Recreate BytesIO handles
    rebuilt: List[Tuple[BytesIO, str]] = [(BytesIO(b), fn) for (b, fn) in file_specs]

    pkg = make_packager(type_test)
    outputs = pkg.process(rebuilt)

    # Normalize to dict[str, bytes]
    out: Dict[str, bytes] = {}
    if isinstance(outputs, dict):
        for name, obj in outputs.items():
            if isinstance(obj, BytesIO):
                out[name] = obj.getvalue()
            elif isinstance(obj, pd.DataFrame):
                out[name] = _df_to_excel_bytes(obj)
            else:
                try:
                    out[name] = obj.getvalue()
                except Exception:
                    out[name] = _df_to_excel_bytes(pd.DataFrame(obj))
    else:
        # Single output fallback
        name = f"{type_test.upper()}_clean.xlsx"
        if isinstance(outputs, BytesIO):
            out[name] = outputs.getvalue()
        elif isinstance(outputs, pd.DataFrame):
            out[name] = _df_to_excel_bytes(outputs)
        else:
            try:
                out[name] = outputs.getvalue()
            except Exception:
                out[name] = _df_to_excel_bytes(pd.DataFrame(outputs))

    return type_test, out


def _run_kqi_only(
    type_test: str,
    file_specs: List[Tuple[bytes, str]],
) -> Tuple[str, Dict[str, bytes]]:
    """
    KQI-only worker:
      - Reads already-clean Excel files (bytes)
      - Summarizes using the proper KQI class
      - Returns {kqi_filename -> bytes}
    """
    factory = _KQI_FACTORY.get(type_test)
    if not factory:
        raise RuntimeError(f"No KQI summarizer for type '{type_test}'")
    summarizer = factory()
    summaries: List[pd.DataFrame] = []

    for b, name in file_specs:
        try:
            df = pd.read_excel(BytesIO(b))
        except Exception as e:
            # Skip unreadable files but keep processing others
            # You could raise instead if you want hard-fail.
            continue

        s = summarizer.summarize(df)  # expected: DataFrame
        if isinstance(s, pd.DataFrame) and not s.empty:
            # Optional: you may want to tag source file
            s = s.copy()
            s["__SourceFile"] = name
            summaries.append(s)

    # If nothing summarized, still return an empty workbook for consistency
    if not summaries:
        empty = pd.DataFrame()
        return type_test, {f"{type_test.upper()}_KQI.xlsx": _df_to_excel_bytes(empty)}

    combined = pd.concat(summaries, ignore_index=True)
    return type_test, {f"{type_test.upper()}_KQI.xlsx": _df_to_excel_bytes(combined)}


def _normalize_to_bytes_map(obj) -> Dict[str, bytes]:
    """
    Normalize aggregator/packager outputs into {name -> bytes}
    Accepts dict[str, BytesIO|bytes|DataFrame|filelike] or single object.
    """

    def _to_bytes(x) -> bytes:
        if isinstance(x, bytes):
            return x
        if isinstance(x, BytesIO):
            return x.getvalue()
        if isinstance(x, pd.DataFrame):
            return _df_to_excel_bytes(x)
        # best-effort: treat file-like
        try:
            return x.getvalue()
        except Exception:
            return _df_to_excel_bytes(pd.DataFrame(x))

    if isinstance(obj, dict):
        return {name: _to_bytes(val) for name, val in obj.items()}
    else:
        return {"output.xlsx": _to_bytes(obj)}


def _run_full_kqi_pipeline(
    type_test: str,
    file_specs: List[Tuple[bytes, str]],
) -> Tuple[str, Dict[str, bytes]]:
    """
    Full pipeline worker for one type:
      1) Aggregate
      2) Clean (Packager)
      3) KQI summarize
    Returns (type_test, {kqi_filename -> bytes})
    """
    # ---------- 1) Aggregate ----------
    agg_inputs: List[Tuple[BytesIO, str]] = [(BytesIO(b), fn) for (b, fn) in file_specs]
    aggregator = make_aggregator(type_test)
    agg_outputs = aggregator.process(agg_inputs)  # dict or single
    agg_bytes_map = _normalize_to_bytes_map(agg_outputs)  # {name -> bytes}

    # ---------- 2) Clean / Packager ----------
    packager = make_packager(type_test)
    pkg_inputs: List[Tuple[BytesIO, str]] = [
        (BytesIO(b), name) for name, b in agg_bytes_map.items()
    ]
    pkg_outputs = packager.process(pkg_inputs)  # dict or single
    clean_bytes_map = _normalize_to_bytes_map(pkg_outputs)  # {clean_name -> bytes}

    # ---------- 3) KQI Summarization ----------
    factory = _KQI_FACTORY.get(type_test)
    if not factory:
        raise RuntimeError(f"No KQI summarizer for type '{type_test}'")
    summarizer = factory()

    # Some types may yield multiple cleaned files; summarize each then combine
    summaries = []
    for clean_name, excel_bytes in clean_bytes_map.items():
        df = pd.read_excel(BytesIO(excel_bytes))
        summary_df = summarizer.summarize(
            df
        )  # each class in kqix implements summarize(df) -> DataFrame
        if isinstance(summary_df, pd.DataFrame) and not summary_df.empty:
            # Option A: one summary per input file
            # out_name = f"{Path(clean_name).stem}_KQI.xlsx"
            # summaries_map[out_name] = _df_to_excel_bytes(summary_df)
            summaries.append(summary_df)

    if not summaries:
        # Make sure we still return a valid (maybe empty) summary workbook
        empty = pd.DataFrame()
        return type_test, {f"{type_test.upper()}_KQI.xlsx": _df_to_excel_bytes(empty)}

    # Default behavior: concatenate all summaries for the type into one file
    combined = pd.concat(summaries, ignore_index=True)
    return type_test, {f"{type_test.upper()}_KQI.xlsx": _df_to_excel_bytes(combined)}


def _df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


def _df_to_excel_buf(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    return buf.getvalue()


# ---------- Worker function (runs in a separate process) ----------
def _run_aggregation(
    type_test: str,
    file_specs: List[Tuple[bytes, str]],
) -> Tuple[str, Union[Dict[str, bytes], bytes]]:
    """
    Run one aggregator for a given type_test in a separate process.

    Parameters
    ----------
    type_test: e.g., 'dns', 'http', ...
    file_specs: List of (file_bytes, filename)

    Returns
    -------x
    (type_test, outputs)
      - If multiple countries: outputs is Dict[country -> excel_bytes]
      - Else: outputs is excel_bytes
    """
    # Recreate BytesIO handles from bytes inside the worker
    rebuilt_specs: List[Tuple[BytesIO, str]] = [
        (BytesIO(b), fn) for (b, fn) in file_specs
    ]

    agg = make_aggregator(type_test)

    outputs = agg.process(rebuilt_specs)

    # Normalize to pure bytes so it’s picklable to return to parent
    if isinstance(outputs, dict):
        norm: Dict[str, bytes] = {}
        for country, obj in outputs.items():
            if isinstance(obj, BytesIO):
                norm[country] = obj.getvalue()
            elif isinstance(obj, pd.DataFrame):
                norm[country] = _df_to_excel_bytes(obj)
            else:
                # Try best-effort: assume file-like
                try:
                    norm[country] = obj.getvalue()
                except Exception as _:
                    # Last resort: serialize DataFrame-like
                    norm[country] = _df_to_excel_bytes(pd.DataFrame(obj))
        return type_test, norm

    # Single output
    if isinstance(outputs, BytesIO):
        return type_test, outputs.getvalue()
    elif isinstance(outputs, pd.DataFrame):
        return type_test, _df_to_excel_bytes(outputs)
    else:
        # Try best-effort serialization
        try:
            return type_test, outputs.getvalue()
        except Exception:
            return type_test, _df_to_excel_bytes(pd.DataFrame(outputs))


def _run_kqi_summarize(
    kqi_type: str,
    file_specs: List[Tuple[bytes, str]],
) -> Tuple[str, Dict[str, bytes]]:
    """
    Worker: merges all files for a kqi_type, runs the right summarizer, returns {filename -> bytes}.
    """
    # 1) Build DataFrame by concatenating all files for this type
    frames: List[pd.DataFrame] = []
    for b, fn in file_specs:
        try:
            df = pd.read_excel(BytesIO(b))
            df["SourceFile"] = os.path.splitext(os.path.basename(fn))[0]
            frames.append(df)
        except Exception as e:
            # Skip bad files but keep going
            print(f"[KQI:{kqi_type}] Skip {fn}: {e}")

    if not frames:
        # Return empty excel so the caller can surface a sensible error
        empty = pd.DataFrame()
        return kqi_type, {f"{kqi_type.upper()}_KQI.xlsx": _df_to_excel_bytes(empty)}

    df_all = pd.concat(frames, ignore_index=True)

    # 2) Make summarizer
    factory = _KQI_FACTORY.get(kqi_type)
    if not factory:
        raise RuntimeError(f"No KQI summarizer for type '{kqi_type}'")

    summarizer = factory()

    # 3) Run summary
    summary_df = summarizer.summarize(df_all)
    out_name = f"{kqi_type.upper()}_KQI.xlsx"
    out_bytes = _df_to_excel_buf(summary_df)

    return kqi_type, {out_name: out_bytes}


@app.post("/v1/aggregator", tags=["endpoints"])
async def agg(
    files: List[UploadFile] = File(..., description="One or more Excel files"),
):
    """Aggregates data from uploaded Excel files based on the filename.

    The function infers the type of test from the filenames and processes
    the files accordingly. It supports

    - DNS testing data (filename contains `dns`)

    - HTTP testing data (filename contains `http`)

    - E-gaming performance data (filename contains `egaming`)

    - Ping/latency data (filename contains `ping`)

    - Streaming quality data (filename contains `streaming`)

    - Video chat data (filename contains `videochat`)

    - Voice M2M data (filename contains `voice_m2m`)

    - Voice OTT data (filename contains `voice_ott`)

    - MOS M2M data (filename contains `mos_m2m`)

    - MOS OTT data (filename contains `mos_ott`)

    The processed data is returned as a downloadable file or a zip archive containing files for each country and type cases if multiple test cases are uploaded.

    you can get the example of the data from this url:

    [RAW CDR new format](https://techbrosgmbhduesseldorf.sharepoint.com/sites/BackofficeCDRPhase3/Freigegebene%20Dokumente/Forms/AllItems.aspx?id=%2Fsites%2FBackofficeCDRPhase3%2FFreigegebene%20Dokumente%2FBackoffice%20CDR%20Phase%203%2FRepository%20EDATools%202025%2FSample%20CDR%20%28Sing%20%26%20Austria%20New%20Format%29%2FRAW%20CDR%20New%20Format&viewid=69e60144%2D9189%2D45cb%2D85bf%2D9042cb52ce53&p=true&ga=1)

    Args:

    - `files (List[UploadFile])`: A list of uploaded Excel files.

    Returns:

    - `StreamingResponse`: A zip file containing the processed data.

    - `JSONResponse`: A JSON response indicating the status of the operation.

    Raises:

    `HTTPException`:

    - `422`: If no files are uploaded.

    - `400`: If uploaded files are empty.

    - `400`: If the type_test cannot be inferred from filenames.

    - `500`: If aggregation fails.
    """
    if not files:
        raise HTTPException(400, "No files uploaded")

    # Organize files by inferred type (store BYTES, not BytesIO, to be picklable)
    typed_files: Dict[str, List[Tuple[bytes, str]]] = {}
    for uf in files:
        content = await uf.read()
        if not content:
            continue

        filename = uf.filename or "uploaded.xlsx"
        inferred_type = None
        for key in _NAME_MAP:
            if key in filename.lower():
                inferred_type = key
                break

        if not inferred_type:
            raise HTTPException(
                status_code=400,
                detail=f"Could not infer type_test from filename: {filename}. "
                f"Please ensure the filename contains the type.",
            )

        typed_files.setdefault(inferred_type, []).append((content, filename))

    if not typed_files:
        raise HTTPException(400, "Uploaded files were empty")

    loop = asyncio.get_running_loop()

    max_workers = max(len(typed_files), (os.cpu_count() or 2))

    try:
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            tasks = [
                loop.run_in_executor(pool, _run_aggregation, type_test, file_specs)
                for type_test, file_specs in typed_files.items()
            ]
            gathered = await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        raise HTTPException(500, f"Parallel execution failed: {e}")

    all_outputs: Dict[str, Union[Dict[str, bytes], bytes]] = {}
    for res in gathered:
        if isinstance(res, Exception):
            raise HTTPException(500, f"Aggregation failed in a worker: {res}")
        type_test, payload = res
        all_outputs[type_test] = payload

    mem_zip = BytesIO()
    with zipfile.ZipFile(mem_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for type_test, outputs in all_outputs.items():
            if isinstance(outputs, dict):
                for country, excel_bytes in outputs.items():
                    fname = f"{type_test.upper()}_{country}_clean.xlsx"
                    zf.writestr(fname, excel_bytes)
            else:  # Single output
                fname = f"{type_test.upper()}_output.xlsx"
                zf.writestr(fname, outputs)

    mem_zip.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="aggregated_outputs.zip"'}
    return StreamingResponse(mem_zip, media_type="application/zip", headers=headers)


@app.post("/v1/cleaner", tags=["endpoints"])
async def split_n_cleansing(
    files: List[UploadFile] = File(
        ...,
        description="One or more Excel files (already in split/cleansed form or raw as expected by the Packager)",
    ),
):
    """
    Split and Clean your test data files.

    **IMPORTANT:** This endpoint expects files that have already been processed through
    the aggregation step (via `/v1/parse` endpoint). Do not upload raw CDR data here.

    This endpoint processes your uploaded Excel files using specialized cleaning algorithms.
    It automatically detects what type of test data you're uploading based on the filename
    and applies the appropriate cleaning and packaging operations.

    **What it does:**
    - Takes your pre-aggregated Excel files (already processed through aggregation)
    - Cleans and standardizes the data format
    - Packages the results into downloadable Excel files
    - Returns everything in a convenient ZIP archive

    **Supported test types (detected from filename):**

    - DNS testing data (filename contains `dns`)

    - HTTP testing data (filename contains `http`)

    - E-gaming performance data (filename contains `egaming`)

    - Ping/latency data (filename contains `ping`)

    - Streaming quality data (filename contains `streaming`)

    - Video chat data (filename contains `videochat`)

    - Voice M2M data (filename contains `voice_m2m`)

    - Voice OTT data (filename contains `voice_ott`)

    - MOS M2M data (filename contains `mos_m2m`)

    - MOS OTT data (filename contains `mos_ott`)


    **How to use:**
    1. First, process your raw data through `/v1/parse` endpoint to aggregate it
    2. Upload the aggregated Excel (.xlsx) files from step 1 to this endpoint
    3. Make sure each filename contains one of the supported test type keywords
    4. Download the ZIP file containing your cleaned data

    **Example filenames:**

    - `dns_test_singapore.xlsx` → Will be processed as DNS data

    - `HTTP_Performance_Austria.xlsx` → Will be processed as HTTP data

    - `streaming_quality_results.xlsx` → Will be processed as Streaming data

    Args:
        files: Pre-aggregated Excel files (output from `/v1/parse` endpoint).
               Each file must have a filename containing a supported test type keyword.

    Returns:
        A ZIP file download containing the cleaned Excel files, ready for analysis.

    Error cases:

        - 400: No files uploaded or files are empty

        - 400: Cannot determine test type from filename (missing keyword)

        - 500: Processing failed due to data format issues
    """
    if not files:
        raise HTTPException(400, "No files uploaded")

    # Group files by inferred or forced type
    typed_files: Dict[str, List[Tuple[bytes, str]]] = {}
    for uf in files:
        content = await uf.read()
        if not content:
            continue

        filename = uf.filename or "uploaded.xlsx"
        inferred_type = None

        for key in _NAME_MAP:
            if key in filename.lower():
                inferred_type = key
                break
        if not inferred_type:
            raise HTTPException(
                status_code=400,
                detail=f"Could not infer type_test from filename: {filename}. "
                f"Either include a known type in the filename or set ?force_type=...",
            )

        typed_files.setdefault(inferred_type, []).append((content, filename))

    if not typed_files:
        raise HTTPException(400, "Uploaded files were empty")
    loop = asyncio.get_running_loop()
    max_workers = max(len(typed_files), (os.cpu_count() or 2))

    try:
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            tasks = [
                loop.run_in_executor(pool, _run_packager_only, type_test, file_specs)
                for type_test, file_specs in typed_files.items()
            ]
            gathered = await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        raise HTTPException(500, f"Parallel execution failed: {e}")

    # Collect results and zip them
    mem_zip = BytesIO()
    with zipfile.ZipFile(mem_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for res in gathered:
            if isinstance(res, Exception):
                raise HTTPException(500, f"Packager failed in a worker: {res}")
            type_test, outputs = res  # Dict[filename -> bytes]
            for final_name, excel_bytes in outputs.items():
                # Namespace inside zip by type for clarity
                safe_name = f"{type_test.upper()}_{final_name}"
                zf.writestr(safe_name, excel_bytes)

    mem_zip.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="packager_outputs.zip"'}
    return StreamingResponse(mem_zip, media_type="application/zip", headers=headers)


@app.post("/v1/excel_merger", tags=["endpoints"])
async def excel_merger(
    files: List[UploadFile] = File(..., description="Two or more Excel files to merge"),
    output_name: str = Query(
        default="merged_output.xlsx", description="Name of the merged Excel file"
    ),
):
    """
    Merge multiple Excel files into a single Excel file.

    Upload any number of .xlsx files and receive a single merged .xlsx back.
    Columns are unioned (outer concat); headers are normalized (trimmed) by the merger.

    Returns:
      - Single Excel file if only one output (typical)
      - ZIP if multiple outputs are ever produced
    """
    if not files:
        raise HTTPException(400, "No files uploaded")

    file_specs: List[Tuple[bytes, str]] = []
    for uf in files:
        content = await uf.read()
        if not content:
            continue
        name = uf.filename or "uploaded.xlsx"
        file_specs.append((content, name))

    if not file_specs:
        raise HTTPException(400, "Uploaded files were empty")

    loop = asyncio.get_running_loop()
    try:
        # run in a process pool in case the merge becomes CPU/memory heavy
        with ProcessPoolExecutor(max_workers=1) as pool:
            result: Dict[str, bytes] = await loop.run_in_executor(
                pool, _run_excel_merger, file_specs, output_name
            )
    except Exception as e:
        raise HTTPException(500, f"Excel merge failed: {e}")

    # Return a single Excel if exactly one output; otherwise zip them
    if len(result) == 1:
        ((fname, excel_bytes),) = result.items()
        headers = {"Content-Disposition": f'attachment; filename="{fname}"'}
        return StreamingResponse(
            BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers,
        )

    # Multiple outputs (unlikely, but supported)
    mem_zip = BytesIO()
    with zipfile.ZipFile(mem_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname, excel_bytes in result.items():
            zf.writestr(fname, excel_bytes)
    mem_zip.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="excel_merged_outputs.zip"'}
    return StreamingResponse(mem_zip, media_type="application/zip", headers=headers)


@app.post("/v1/kqi_clean", tags=["endpoints"])
async def kqi_from_clean(
    files: List[UploadFile] = File(
        ..., description="CLEAN Excel files (packager outputs). Runs KQI only."
    ),
):
    """
    KQI-only pipeline: read already-clean Excel files, compute KQI, return KQI workbook(s).

    Filenames must contain one of:
    {', '.join(_KQI_FACTORY.keys())}
    """
    if not files:
        raise HTTPException(400, "No files uploaded")

    # Group uploaded CLEAN files by inferred type
    typed_files: Dict[str, List[Tuple[bytes, str]]] = {}
    for uf in files:
        content = await uf.read()
        if not content:
            continue

        filename = uf.filename or "uploaded.xlsx"
        inferred_type = None
        for key in _KQI_FACTORY.keys():
            if key in filename.lower():
                inferred_type = key
                break

        if not inferred_type:
            raise HTTPException(
                status_code=400,
                detail=f"Could not infer type_test for KQI from filename: {filename}. "
                f"Must contain one of: {', '.join(_KQI_FACTORY.keys())}",
            )

        typed_files.setdefault(inferred_type, []).append((content, filename))

    if not typed_files:
        raise HTTPException(400, "Uploaded files were empty")

    # Run KQI per type in parallel
    loop = asyncio.get_running_loop()
    max_workers = max(len(typed_files), (os.cpu_count() or 2))
    try:
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            tasks = [
                loop.run_in_executor(pool, _run_kqi_only, type_test, file_specs)
                for type_test, file_specs in typed_files.items()
            ]
            gathered = await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        raise HTTPException(500, f"KQI-only pipeline execution failed: {e}")

    # Collect results into a ZIP
    mem_zip = BytesIO()
    with zipfile.ZipFile(mem_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for res in gathered:
            if isinstance(res, Exception):
                raise HTTPException(500, f"KQI-only worker failed: {res}")
            type_test, outputs_map = res  # {kqi_filename -> bytes}
            for fname, excel_bytes in outputs_map.items():
                # Keep names as-is; if you prefer a prefix use f"{type_test.upper()}_{fname}"
                zf.writestr(fname, excel_bytes)

    mem_zip.seek(0)
    headers = {
        "Content-Disposition": 'attachment; filename="kqi_from_clean_outputs.zip"'
    }
    return StreamingResponse(mem_zip, media_type="application/zip", headers=headers)


# --- NEW ENDPOINT: SPLIT_N_CLEANSING ---


@app.post("/v1/pipeline_cleaner", tags=["pipeline"])
async def pipeline_cleaner(
    files: List[UploadFile] = File(..., description="One or more Excel files"),
):
    """
    Complete data processing pipeline: Aggregate → Clean & Parsing

    This is the full end-to-end processing pipeline that takes your raw test data files,
    aggregates them by country and test type, then splits and cleans the results.
    Perfect for processing fresh data exports that need both aggregation and cleaning.

    **What it does:**
    1. **Aggregate**: Combines and organizes your raw data by country and test type
    2. **Clean**: Standardizes data formats and removes inconsistencies
    4. **Deliver**: Returns all results in a single ZIP download

    **When to use this endpoint:**
    - You have raw CDR (Call Detail Record) data that needs full processing
    - Your data needs to be grouped by countries or regions
    - You want both aggregation and cleaning in one step
    - You're processing fresh exports from network monitoring tools

    **Supported test types (detected from filename):**

    - DNS testing data (filename contains `dns`)

    - HTTP testing data (filename contains `http`)

    - E-gaming performance data (filename contains `egaming`)

    - Ping/latency data (filename contains `ping`)

    - Streaming quality data (filename contains `streaming`)

    - Video chat data (filename contains `videochat`)

    - Voice M2M data (filename contains `voice_m2m`)

    - Voice OTT data (filename contains `voice_ott`)

    - MOS M2M data (filename contains `mos_m2m`)

    - MOS OTT data (filename contains `mos_ott`)

    **How to use:**
    1. Upload your raw Excel data files
    2. Ensure filenames contain test type keywords (e.g., "dns", "http", etc.)
    3. Wait for processing to complete (runs in parallel for speed)
    4. Download the ZIP containing your processed data

    **Example workflow:**
    Upload: `raw_dns_data_singapore.xlsx`, `raw_http_data_austria.xlsx`
    →  Processing aggregates data by country and test type
    →  Download: `pipeline_outputs.zip` containing clean, analysis-ready files

    **Sample data reference:**

    For examples of expected input formats, see: [RAW CDR new format](https://techbrosgmbhduesseldorf.sharepoint.com/sites/BackofficeCDRPhase3/Freigegebene%20Dokumente/Forms/AllItems.aspx?id=%2Fsites%2FBackofficeCDRPhase3%2FFreigegebene%20Dokumente%2FBackoffice%20CDR%20Phase%203%2FRepository%20EDATools%202025%2FSample%20CDR%20%28Sing%20%26%20Austria%20New%20Format%29%2FRAW%20CDR%20New%20Format&viewid=69e60144%2D9189%2D45cb%2D85bf%2D9042cb52ce53&p=true&ga=1)

    Args:

        files: Raw Excel files containing test data. Each filename must include
               a recognizable test type keyword for automatic processing.

    Returns:

        A ZIP file download with fully processed, analysis-ready Excel files
        organized by test type and country.

    Error cases:

        - 400: No files uploaded, empty files, or unrecognizable test type in filename

        - 500: Processing pipeline failed (data format issues, processing errors)

    **Performance note:**
    Processing runs in parallel across different test types for optimal speed.
    Large datasets may take a few minutes to complete.
    """
    if not files:
        raise HTTPException(400, "No files uploaded")

    # Group files by inferred type_test (store raw bytes for pickling)
    typed_files: Dict[str, List[Tuple[bytes, str]]] = {}
    for uf in files:
        content = await uf.read()
        if not content:
            continue

        filename = uf.filename or "uploaded.xlsx"
        inferred_type = None
        for key in _NAME_MAP:
            if key in filename.lower():
                inferred_type = key
                break

        if not inferred_type:
            raise HTTPException(
                status_code=400,
                detail=f"Could not infer type_test from filename: {filename}. "
                f"Ensure the filename contains one of: {', '.join(_NAME_MAP.keys())}",
            )

        typed_files.setdefault(inferred_type, []).append((content, filename))

    if not typed_files:
        raise HTTPException(400, "Uploaded files were empty")

    # Run pipeline in parallel across types
    loop = asyncio.get_running_loop()
    max_workers = max(len(typed_files), (os.cpu_count() or 2))

    try:
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            tasks = [
                loop.run_in_executor(
                    pool, _run_split_n_cleansing, type_test, file_specs
                )
                for type_test, file_specs in typed_files.items()
            ]
            gathered = await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        raise HTTPException(500, f"Parallel execution failed: {e}")

    # Collect results and zip them
    mem_zip = BytesIO()
    with zipfile.ZipFile(mem_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for res in gathered:
            if isinstance(res, Exception):
                raise HTTPException(500, f"Pipeline failed in a worker: {res}")
            type_test, outputs_dict = res  # outputs_dict: Dict[filename -> bytes]
            for final_name, excel_bytes in outputs_dict.items():
                # Namespace the file inside the zip by type
                safe_name = f"{type_test.upper()}_{final_name}"
                zf.writestr(safe_name, excel_bytes)

    mem_zip.seek(0)
    headers = {
        "Content-Disposition": 'attachment; filename="split_n_cleansing_outputs.zip"'
    }
    return StreamingResponse(mem_zip, media_type="application/zip", headers=headers)


@app.post("/v1/pipeline_kqi", tags=["pipeline"])
async def kqi_pipeline(
    files: List[UploadFile] = File(
        ..., description="RAW Excel files. This endpoint will Aggregate → Clean → KQI."
    ),
):
    """
    Full KQI pipeline: Aggregate → Clean (Packager) → KQI summarization.

    Upload RAW files (filenames must contain one of: {', '.join(_KQI_FACTORY.keys())})
    """
    if not files:
        raise HTTPException(400, "No files uploaded")

    # Group raw files by inferred type_test (from filename)
    typed_files: Dict[str, List[Tuple[bytes, str]]] = {}
    for uf in files:
        content = await uf.read()
        if not content:
            continue

        filename = uf.filename or "uploaded.xlsx"
        inferred_type = None
        for key in _KQI_FACTORY.keys():
            if key in filename.lower():
                inferred_type = key
                break
        if not inferred_type:
            raise HTTPException(
                status_code=400,
                detail=f"Could not infer type_test for KQI from filename: {filename}. "
                f"Must contain one of: {', '.join(_KQI_FACTORY.keys())}",
            )

        typed_files.setdefault(inferred_type, []).append((content, filename))

    if not typed_files:
        raise HTTPException(400, "Uploaded files were empty")

    # Run each type in parallel processes
    loop = asyncio.get_running_loop()
    max_workers = max(len(typed_files), (os.cpu_count() or 2))
    try:
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            tasks = [
                loop.run_in_executor(
                    pool, _run_full_kqi_pipeline, type_test, file_specs
                )
                for type_test, file_specs in typed_files.items()
            ]
            gathered = await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        raise HTTPException(500, f"KQI pipeline execution failed: {e}")

    # Collect results and zip them
    mem_zip = BytesIO()
    with zipfile.ZipFile(mem_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for res in gathered:
            if isinstance(res, Exception):
                raise HTTPException(500, f"KQI pipeline failed in a worker: {res}")
            type_test, outputs_map = res  # {kqi_filename -> bytes}
            for fname, excel_bytes in outputs_map.items():
                # If you prefer to prefix with type: safe_name = f"{type_test.upper()}_{fname}"
                zf.writestr(fname, excel_bytes)

    mem_zip.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="kqi_outputs.zip"'}
    return StreamingResponse(mem_zip, media_type="application/zip", headers=headers)


@app.get("/health", tags=["health"])
def health():
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("services.eda_tools_api:app", host="0.0.0.0", port=8000, reload=True)
