import inspect
import os
import sys
import zipfile
from io import BytesIO
from typing import Dict, List, Tuple, Union

import asyncio
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from configparser import ConfigParser

from concurrent.futures import ProcessPoolExecutor

path_this = os.path.dirname(os.path.abspath(__file__))
path_project = os.path.dirname(os.path.join(path_this, ".."))
path_root = os.path.dirname(os.path.join(path_this, "../.."))
sys.path.append(path_root)
sys.path.append(path_project)
sys.path.append(path_this)

import parsing_tools as parsing
import split_n_cleansing_tools as cleaner

app = FastAPI(
    title="Techbros EDA Tools Automation API",
    description="API for automating EDA tools data aggregation and processing.",
    version="1.0.0",
)
config = ConfigParser()
config.read(os.path.join(path_root, 'config.ini'))
MCC_MNC_PATH = os.path.join(path_root, config.get('default', 'mcc_mnc_path'))
TEST_CASE_PATH = os.path.join(path_root,config.get('default', 'test_case_path'))

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




app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def make_aggregator(kind: str, *, mcc_mnc_df=None, test_case_df=None):
    kind = (kind or "").lower()

    mcc_mnc_df = pd.read_excel(MCC_MNC_PATH) if mcc_mnc_df is None else mcc_mnc_df
    test_case_df = pd.read_excel(TEST_CASE_PATH) if test_case_df is None else test_case_df

    try:
        cls_names = _NAME_MAP[kind]          # FIX: use kind, not kind[0]
        cls_name = cls_names[0]              # Aggregator class name
        cls = getattr(parsing, cls_name)
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Unknown type_test: {kind}")

    return cls(mcc_mnc_df=mcc_mnc_df, test_case_df=test_case_df)


def make_packager(kind: str):
    """Return the packager class instance from `split_n_cleansing_tools`."""
    kind = (kind or "").lower()
    try:
        cls_names = _NAME_MAP[kind]
        cls_name = cls_names[1]              # Packager class name
        cls = getattr(cleaner, cls_name)
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Unknown type_test for packager: {kind}")
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
    rebuilt_specs: List[Tuple[BytesIO, str]] = [(BytesIO(b), fn) for (b, fn) in file_specs]

    # 1) Aggregate
    agg = make_aggregator(type_test)
    agg_outputs = agg.process(rebuilt_specs)
    # Normalize aggregator outputs to dict[str, bytes]
    if isinstance(agg_outputs, BytesIO):
        agg_outputs = {"output.xlsx": agg_outputs.getvalue()}
    elif isinstance(agg_outputs, pd.DataFrame):
        agg_outputs = {"output.xlsx": _df_to_excel_bytes(agg_outputs)}
    elif not isinstance(agg_outputs, dict):
        # best-effort
        try:
            agg_outputs = {"output.xlsx": agg_outputs.getvalue()}
        except Exception:
            agg_outputs = {"output.xlsx": _df_to_excel_bytes(pd.DataFrame(agg_outputs))}

    # 2) Run packager: convert aggregated bytes into "files" expected by packagers
    pkg = make_packager(type_test)
    pkg_inputs: List[Tuple[BytesIO, str]] = []
    for name, excel_bytes in agg_outputs.items():
        pkg_inputs.append((BytesIO(excel_bytes), name))

    pkg_outputs = pkg.process(pkg_inputs)

    # 3) Normalize packager outputs to dict[str, bytes]
    out: Dict[str, bytes] = {}
    if isinstance(pkg_outputs, dict):
        for final_name, obj in pkg_outputs.items():
            if isinstance(obj, BytesIO):
                out[final_name] = obj.getvalue()
            elif isinstance(obj, pd.DataFrame):
                out[final_name] = _df_to_excel_bytes(obj)
            else:
                try:
                    out[final_name] = obj.getvalue()
                except Exception:
                    out[final_name] = _df_to_excel_bytes(pd.DataFrame(obj))
    else:
        # Single output (rare in packagers, but keep parity)
        final_name = f"{type_test.upper()}_clean.xlsx"
        if isinstance(pkg_outputs, BytesIO):
            out[final_name] = pkg_outputs.getvalue()
        elif isinstance(pkg_outputs, pd.DataFrame):
            out[final_name] = _df_to_excel_bytes(pkg_outputs)
        else:
            try:
                out[final_name] = pkg_outputs.getvalue()
            except Exception:
                out[final_name] = _df_to_excel_bytes(pd.DataFrame(pkg_outputs))

    return type_test, out

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



def _df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    df.to_excel(buf, index=False)
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
    rebuilt_specs: List[Tuple[BytesIO, str]] = [(BytesIO(b), fn) for (b, fn) in file_specs]

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


@app.post("/v1/parse", tags=["endpoints"])
async def agg(
    files: List[UploadFile] = File(..., description="One or more Excel files"),
):
    """Aggregates data from uploaded Excel files based on the filename.

    The function infers the type of test from the filenames and processes
    the files accordingly. It supports

    - `dns`

    - `http`

    - `ping`

    - `egaming`

    - `streaming`

    - `videochat`

    - `voice_m2m`

    - `voice_ott`

    - `mos_m2m`

    - `mos_ott`

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

@app.post("/v1/packager", tags=["endpoints"])
async def packager_only(
    files: List[UploadFile] = File(..., description="One or more Excel files (already in split/cleansed form or raw as expected by the Packager)"),
    force_type: str | None = Query(default=None, description=f"Force a type_test for all files. One of: {', '.join(_NAME_MAP.keys())}"),
):
    """
    Run only the packager (split_n_cleansing_tools.<*Packager>) on uploaded files.
    This skips the aggregator stage and directly processes inputs with the packager.
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
        if force_type:
            inferred_type = force_type.lower()
            if inferred_type not in _NAME_MAP:
                raise HTTPException(400, f"force_type '{force_type}' is not supported. Allowed: {', '.join(_NAME_MAP.keys())}")
        else:
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

    # Run packagers in parallel by type
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
                safe_name = f"{type_test.upper()}__{final_name}"
                zf.writestr(safe_name, excel_bytes)

    mem_zip.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="packager_outputs.zip"'}
    return StreamingResponse(mem_zip, media_type="application/zip", headers=headers)
# --- NEW ENDPOINT: SPLIT_N_CLEANSING ---

@app.post("/v1/split_n_cleansing", tags=["pipeline"])
async def split_n_cleansing(
    files: List[UploadFile] = File(..., description="One or more Excel files"),
):
    """
    End-to-end pipeline:
      - Aggregate uploaded files via parsing_tools.<*Aggregator>
      - Feed results to split_n_cleansing_tools.<*Packager>
      - Return final packaged outputs (zipped)
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
                loop.run_in_executor(pool, _run_split_n_cleansing, type_test, file_specs)
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
                safe_name = f"{type_test.upper()}__{final_name}"
                zf.writestr(safe_name, excel_bytes)

    mem_zip.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="split_n_cleansing_outputs.zip"'}
    return StreamingResponse(mem_zip, media_type="application/zip", headers=headers)


@app.get("/health", tags=["health"])
def health():
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("services.eda_tools_api:app", host="0.0.0.0", port=8000, reload=True)
