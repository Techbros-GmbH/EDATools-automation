import inspect
import os
import sys
import zipfile
from io import BytesIO
from typing import List

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

path_this = os.path.dirname(os.path.abspath(__file__))
path_project = os.path.dirname(os.path.join(path_this, ".."))
path_root = os.path.dirname(os.path.join(path_this, "../.."))
sys.path.append(path_root)
sys.path.append(path_project)
sys.path.append(path_this)

import parsing_tools as tools

app = FastAPI(
    title="EDA Tools Automation API",
    description="API for automating EDA tools data aggregation and processing.",
    version="1.0.0",
)

_NAME_MAP = {
    "dns": "DNSAggregator",
    "http": "HTTPAggregator",
    "egaming": "EgamingAggregator",
    "ping": "PingAggregator",
    "streaming": "StreamingAggregator",
    "video_chat": "VideoChatAggregator",
    "videochat": "VideoChatAggregator",
    "voice_m2m": "VoiceM2MAggregator",
    "voice_ott": "VoiceOTTAggregator",
    "mos_m2m": "MOSM2MAggregator",
    "mos_ott": "MOSOTTAggregator",
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
    try:
        cls = getattr(tools, _NAME_MAP[kind])
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Unknown type_test: {kind}")

    kwargs = {}
    sig = inspect.signature(cls.__init__)
    if "mcc_mnc_df" in sig.parameters:
        kwargs["mcc_mnc_df"] = mcc_mnc_df
    if "test_case_df" in sig.parameters:
        kwargs["test_case_df"] = test_case_df
    return cls(**kwargs)


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

    The processed data is returned as a downloadable file or a zip archive containing files for each country.

    Args:

    - `files (List[UploadFile])`: A list of uploaded Excel files.

    Returns:

    - `StreamingResponse`: A zip file containing the processed data.

    - `JSONResponse`: A JSON response indicating the status of the operation.

    Raises:

    `HTTPException`:

    - `400: If no files are uploaded.`

    - `400: If uploaded files are empty.`

    - `400: If filenames contain conflicting type indications.`

    - `400: If the type_test cannot be inferred from filenames.`

    - `500: If aggregation fails.`
    """
    if not files:
        raise HTTPException(400, "No files uploaded")

    file_specs = []
    for uf in files:
        content = await uf.read()
        if not content:
            continue
        buf = BytesIO(content)
        buf.seek(0)
        file_specs.append((buf, uf.filename))

    if not file_specs:
        raise HTTPException(400, "Uploaded files were empty")

    # Determine type_test from filenames
    inferred_type = None
    for filename in [spec[1] for spec in file_specs]:
        for key in _NAME_MAP:
            if key in filename.lower():
                if inferred_type is not None and inferred_type != key:
                    raise HTTPException(
                        status_code=400,
                        detail="Filenames contain conflicting type indications.  Please upload files of only one type or specify the type explicitly.",
                    )
                inferred_type = key
    if not inferred_type:
        raise HTTPException(
            status_code=400,
            detail="Could not infer type_test from filenames. Please ensure filenames contain the type or specify the type explicitly.",
        )
    type_test = inferred_type

    agg = make_aggregator(
        type_test
    )  # mcc_mnc_df/test_case_df can be wired later if needed

    try:
        outputs = agg.process(file_specs)
    except Exception as e:
        raise HTTPException(500, f"Aggregation failed: {e}")

    # Normalize outputs to a downloadable file
    if isinstance(outputs, dict): 
        mem_zip = BytesIO()
        with zipfile.ZipFile(mem_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for key, bio in outputs.items():
                bio.seek(0)
                fname = f"{type_test.upper()}_{key}_clean.xlsx"
                zf.writestr(fname, bio.read())
        mem_zip.seek(0)
        headers = {
            "Content-Disposition": f'attachment; filename="{type_test.lower()}_outputs.zip"'
        }
        return StreamingResponse(mem_zip, media_type="application/zip", headers=headers)

    if isinstance(outputs, BytesIO):
        outputs.seek(0)
        headers = {
            "Content-Disposition": f'attachment; filename="{type_test.lower()}_output.xlsx"'
        }
        return StreamingResponse(
            outputs,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers,
        )

    if isinstance(outputs, pd.DataFrame):
        buf = BytesIO()
        outputs.to_excel(buf, index=False)
        buf.seek(0)
        headers = {
            "Content-Disposition": f'attachment; filename="{type_test.lower()}_output.xlsx"'
        }
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers,
        )

    # Fallback
    return JSONResponse({"status": "ok", "detail": f"done ({type(outputs)})"})


@app.get("/health")
def health():
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("services.eda_tools_api:app", host="0.0.0.0", port=8000, reload=True)
