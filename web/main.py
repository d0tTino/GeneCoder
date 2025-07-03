import os
import json
import hashlib
import secrets
from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pathlib import Path
from pydantic import BaseModel
from dataclasses import asdict
import asyncio
import base64
import re

from genecoder.options import EncodeOptions
from genecoder import perform_encoding, perform_decoding
from genecoder.formats import from_fasta
from genecoder.encoders import calculate_gc_content, decode_base4_direct
from genecoder.utils import get_max_homopolymer_length, get_temp_dir
from genecoder.plotting import (
    calculate_windowed_gc_content,
    identify_homopolymer_regions,
    generate_sequence_analysis_plot,
)
from genecoder.error_simulation import introduce_errors
from genecoder.app_helpers import EncodeResult, DecodeResult
from genecoder.report import (
    encode_to_markdown,
    decode_to_markdown,
    encode_to_html,
    decode_to_html,
)
from typing import cast
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
import redis.asyncio as redis

DNA_RE = re.compile(r"^[ACGT]+$")


def bit_error_rate(original: bytes, recovered: bytes) -> float:
    """Return the bit error rate between two byte strings."""
    total_bits = len(original) * 8
    min_len = min(len(original), len(recovered))
    errors = 0
    for o, r in zip(original[:min_len], recovered[:min_len]):
        errors += (o ^ r).bit_count()
    if len(recovered) < len(original):
        errors += (len(original) - len(recovered)) * 8
    return errors / total_bits if total_bits else 0.0

API_TOKEN: str | None = os.getenv("GENECODER_API_TOKEN")
CORS_ORIGINS = os.getenv("GENECODER_CORS_ORIGINS", "*")
security = HTTPBearer(auto_error=False)


def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> None:
    if credentials is None or credentials.credentials != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing token")

app = FastAPI(title="GeneCoder Web")
origins = [origin.strip() for origin in CORS_ORIGINS.split(",") if origin.strip()]

REDIS_URL = os.getenv("GENECODER_REDIS_URL")


@app.on_event("startup")
async def _startup() -> None:
    global API_TOKEN
    if API_TOKEN is None:
        API_TOKEN = secrets.token_urlsafe(16)
        print(f"Generated API token: {API_TOKEN}")
    if REDIS_URL:
        r = redis.from_url(
            REDIS_URL, encoding="utf-8", decode_responses=True
        )  # type: ignore[no-untyped-call]
        await FastAPILimiter.init(r)


@app.on_event("shutdown")
async def _shutdown() -> None:
    if FastAPILimiter.redis:
        await FastAPILimiter.close()


async def rate_limit(request: Request, response: Response) -> None:
    if FastAPILimiter.redis:
        limiter = RateLimiter(times=5, seconds=1)
        await limiter(request, response)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Mount the React-based helix viewer as a static directory
helix_ui_dir = Path(__file__).parent / "helix-ui"
app.mount("/helix-ui", StaticFiles(directory=helix_ui_dir), name="helix-ui")

index_path = static_dir / "index.html"
helix_index_path = helix_ui_dir / "dist" / "index.html"
if not helix_index_path.is_file():
    helix_index_path = helix_ui_dir / "index.html"

dashboard_index_path = helix_ui_dir / "dist" / "dashboard.html"
if not dashboard_index_path.is_file():
    dashboard_index_path = helix_ui_dir / "dashboard.html"

@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return index_path.read_text(encoding="utf-8")


@app.get("/helix", response_class=HTMLResponse)
async def helix() -> str:
    """Return the React-based helix viewer."""
    return helix_index_path.read_text(encoding="utf-8")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> str:
    """Return the React-based dashboard interface."""
    return dashboard_index_path.read_text(encoding="utf-8")


class EncodeOptionsModel(BaseModel):
    method: str
    add_parity: bool = False
    k_value: int = 7
    fec_method: str = "None"
    gc_min: float = 0.45
    gc_max: float = 0.55
    max_homopolymer: int = 3
    window_size: int = 50
    step_size: int = 10
    min_homopolymer_len: int = 4
    alphabet: str = "base4"


class EncodeRequest(BaseModel):
    data: str
    options: EncodeOptionsModel


class DecodeRequest(BaseModel):
    fasta_data: str
    alphabet: str = "base4"


class AnalyzeRequest(BaseModel):
    fasta_data: str
    window_size: int = 50
    step_size: int = 10


class DashboardMetricsRequest(BaseModel):
    dna_sequence: str
    window_size: int = 50
    step_size: int = 10
    min_homopolymer_len: int = 4


class ReportRequest(BaseModel):
    data: dict[str, object]
    type: str  # "encode" or "decode"
    format: str = "markdown"


class DecodeAIRequest(BaseModel):
    """Request model for the AI-based decode endpoint."""

    encoded: str
    info: dict[str, object]

@app.post("/encode")
async def encode(
    req: EncodeRequest,
    _: None = Depends(verify_token),
) -> dict[str, object]:
    data_bytes = base64.b64decode(req.data.encode("utf-8"), validate=True)
    opts = EncodeOptions(**req.options.model_dump())
    result = await asyncio.to_thread(perform_encoding, data_bytes, opts)
    return asdict(result)


@app.post("/decode")
async def decode(
    req: DecodeRequest,
    _: None = Depends(verify_token),
) -> dict[str, object]:
    result = await asyncio.to_thread(
        perform_decoding, req.fasta_data, req.alphabet
    )
    return {
        "decoded_bytes": base64.b64encode(result.decoded_bytes).decode("utf-8"),
        "status_message": result.status_message,
        "fec_info": result.fec_info,
    }


@app.post("/decode/ai")
async def decode_ai(req: DecodeAIRequest) -> dict[str, object]:
    """Decode data using the optional DNAformer model."""

    try:
        from genecoder.dnaformer_codec import decode_data_dnaformer
    except Exception as exc:  # pragma: no cover - optional dependency
        raise HTTPException(status_code=503, detail="DNAformer not available") from exc

    encoded = base64.b64decode(req.encoded, validate=True)
    decoded, corrected = await asyncio.to_thread(
        decode_data_dnaformer, encoded, req.info
    )
    return {
        "decoded_bytes": base64.b64encode(decoded).decode("utf-8"),
        "corrected": corrected,
    }


@app.post("/analyze")
async def analyze(req: AnalyzeRequest) -> dict[str, object]:
    parsed = from_fasta(req.fasta_data)
    if not parsed:
        raise HTTPException(status_code=400, detail="No valid FASTA records found")
    _, sequence = parsed[0]
    gc = calculate_gc_content(sequence)
    length = len(sequence)
    max_hp = get_max_homopolymer_length(sequence)
    _, gc_values = calculate_windowed_gc_content(
        sequence, req.window_size, req.step_size
    )
    avg_gc = sum(gc_values) / len(gc_values) if gc_values else 0.0
    metrics = {
        "length": length,
        "gc_content": gc,
        "max_homopolymer": max_hp,
        "windowed_gc": {
            "min": min(gc_values) if gc_values else 0.0,
            "max": max(gc_values) if gc_values else 0.0,
            "avg": avg_gc,
        },
    }
    return metrics


@app.post("/dashboard/metrics")
async def dashboard_metrics(
    req: DashboardMetricsRequest,
    _: None = Depends(verify_token),
) -> dict[str, object]:
    seq = req.dna_sequence
    if not DNA_RE.fullmatch(seq):
        raise HTTPException(status_code=400, detail="Invalid DNA sequence")
    gc = calculate_gc_content(seq)
    max_hp = get_max_homopolymer_length(seq)
    gc_data = calculate_windowed_gc_content(seq, req.window_size, req.step_size)
    hp_regions = identify_homopolymer_regions(seq, req.min_homopolymer_len)
    buf = generate_sequence_analysis_plot(gc_data, hp_regions, len(seq))
    plot_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    buf.close()
    try:
        orig_bytes, _ = decode_base4_direct(seq)
        corrupted = introduce_errors(seq, substitution_prob=0.05)
        dec_bytes, _ = decode_base4_direct(corrupted)
        ber = bit_error_rate(orig_bytes, dec_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "gc_content": gc,
        "max_homopolymer": max_hp,
        "error_rate": ber,
        "plot": plot_b64,
    }


class PlotDataRequest(BaseModel):
    """Request model for dashboard heatmap data."""

    dna_sequence: str
    window_size: int = 50
    step_size: int = 10


def _homopolymer_lengths(seq: str) -> list[int]:
    """Return the length of the homopolymer each base belongs to."""

    lengths: list[int] = [0] * len(seq)
    i = 0
    n = len(seq)
    while i < n:
        j = i
        while j < n and seq[j] == seq[i]:
            j += 1
        run_len = j - i
        for k in range(i, j):
            lengths[k] = run_len
        i = j
    return lengths


@app.post("/dashboard/plot-data")
async def dashboard_plot_data(
    req: PlotDataRequest,
    _: None = Depends(verify_token),
) -> dict[str, object]:
    """Return windowed GC content and homopolymer lengths."""

    seq = req.dna_sequence
    if not DNA_RE.fullmatch(seq):
        raise HTTPException(status_code=400, detail="Invalid DNA sequence")
    starts, gc_values = calculate_windowed_gc_content(
        seq, req.window_size, req.step_size
    )
    hp_lengths = _homopolymer_lengths(seq)
    return {
        "gc_positions": starts,
        "gc_values": gc_values,
        "hp_lengths": hp_lengths,
    }


@app.post("/report")
async def report(req: ReportRequest) -> dict[str, str]:
    if req.type == "encode":
        result = EncodeResult(**req.data)
        if req.format == "markdown":
            text = encode_to_markdown(result)
        else:
            text = encode_to_html(result)
    else:
        data = req.data.copy()
        if isinstance(data.get("decoded_bytes"), str):
            data["decoded_bytes"] = base64.b64decode(
                cast(str, data["decoded_bytes"])
            )
        result = DecodeResult(**data)
        if req.format == "markdown":
            text = decode_to_markdown(result)
        else:
            text = decode_to_html(result)
    return {"report": text}


class ChunkUploadRequest(BaseModel):
    file_id: str
    offset: int
    data: str


@app.post("/upload-chunk")
async def upload_chunk(
    req: ChunkUploadRequest,
    request: Request,
    response: Response,
) -> dict[str, str]:
    if FastAPILimiter.redis:
        await rate_limit(request, response)
    base_dir = get_temp_dir() / "chunks" / req.file_id
    base_dir.mkdir(parents=True, exist_ok=True)
    chunk_bytes = base64.b64decode(req.data.encode("utf-8"), validate=True)
    chunk_path = base_dir / f"{req.offset}.chunk"
    with open(chunk_path, "wb") as f:
        f.write(chunk_bytes)
    manifest_path = base_dir / "upload.manifest"
    h = hashlib.sha256(chunk_bytes).hexdigest()
    with open(manifest_path, "a", encoding="utf-8") as mf:
        mf.write(json.dumps({"offset": req.offset, "hash": h}) + "\n")
    return {"status": "ok", "hash": h}


@app.get("/download-chunk")
async def download_chunk(
    file_id: str,
    offset: int,
    request: Request,
    response: Response,
) -> dict[str, str]:
    if FastAPILimiter.redis:
        await rate_limit(request, response)
    chunk_path = get_temp_dir() / "chunks" / file_id / f"{offset}.chunk"
    if not chunk_path.is_file():
        raise HTTPException(status_code=404, detail="Chunk not found")
    data = chunk_path.read_bytes()
    return {"offset": str(offset), "data": base64.b64encode(data).decode("utf-8")}
