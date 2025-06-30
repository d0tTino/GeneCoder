from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException
from pathlib import Path
from pydantic import BaseModel
from dataclasses import asdict
import asyncio
import base64

from genecoder.options import EncodeOptions
from genecoder import perform_encoding, perform_decoding
from genecoder.formats import from_fasta
from genecoder.encoders import calculate_gc_content
from genecoder.utils import get_max_homopolymer_length
from genecoder.plotting import calculate_windowed_gc_content
from genecoder.app_helpers import EncodeResult, DecodeResult
from genecoder.report import (
    encode_to_markdown,
    decode_to_markdown,
    encode_to_html,
    decode_to_html,
)
from typing import cast

app = FastAPI(title="GeneCoder Web")

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Mount the React-based helix viewer as a static directory
helix_ui_dir = Path(__file__).parent / "helix-ui"
app.mount("/helix-ui", StaticFiles(directory=helix_ui_dir), name="helix-ui")

index_path = static_dir / "index.html"
helix_index_path = helix_ui_dir / "dist" / "index.html"
if not helix_index_path.is_file():
    helix_index_path = helix_ui_dir / "index.html"

@app.get("/", response_class=HTMLResponse)  # type: ignore[misc]
async def index() -> str:
    return index_path.read_text(encoding="utf-8")


@app.get("/helix", response_class=HTMLResponse)  # type: ignore[misc]
async def helix() -> str:
    """Return the React-based helix viewer."""
    return helix_index_path.read_text(encoding="utf-8")


class EncodeOptionsModel(BaseModel):  # type: ignore[misc]
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


class EncodeRequest(BaseModel):  # type: ignore[misc]
    data: str
    options: EncodeOptionsModel


class DecodeRequest(BaseModel):  # type: ignore[misc]
    fasta_data: str
    alphabet: str = "base4"


class AnalyzeRequest(BaseModel):  # type: ignore[misc]
    fasta_data: str
    window_size: int = 50
    step_size: int = 10


class ReportRequest(BaseModel):  # type: ignore[misc]
    data: dict[str, object]
    type: str  # "encode" or "decode"
    format: str = "markdown"


class DecodeAIRequest(BaseModel):  # type: ignore[misc]
    """Request model for the AI-based decode endpoint."""

    encoded: str
    info: dict[str, object]

@app.post("/encode")  # type: ignore[misc]
async def encode(req: EncodeRequest) -> dict[str, object]:
    data_bytes = base64.b64decode(req.data.encode("utf-8"), validate=True)
    opts = EncodeOptions(**req.options.model_dump())
    result = await asyncio.to_thread(perform_encoding, data_bytes, opts)
    return asdict(result)


@app.post("/decode")  # type: ignore[misc]
async def decode(req: DecodeRequest) -> dict[str, object]:
    result = await asyncio.to_thread(
        perform_decoding, req.fasta_data, req.alphabet
    )
    return {
        "decoded_bytes": base64.b64encode(result.decoded_bytes).decode("utf-8"),
        "status_message": result.status_message,
        "fec_info": result.fec_info,
    }


@app.post("/decode/ai")  # type: ignore[misc]
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


@app.post("/analyze")  # type: ignore[misc]
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


@app.post("/report")  # type: ignore[misc]
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
