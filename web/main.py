from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel
from dataclasses import asdict
import asyncio
import base64

from genecoder import EncodeOptions, perform_encoding, perform_decoding

app = FastAPI(title="GeneCoder Web")

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

index_path = static_dir / "index.html"

@app.get("/", response_class=HTMLResponse)  # type: ignore[misc]
async def index() -> str:
    return index_path.read_text(encoding="utf-8")


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


@app.post("/encode")
async def encode(req: EncodeRequest) -> dict:
    data_bytes = base64.b64decode(req.data.encode("utf-8"), validate=True)
    opts = EncodeOptions(**req.options.model_dump())
    result = await asyncio.to_thread(perform_encoding, data_bytes, opts)
    return asdict(result)


@app.post("/decode")
async def decode(req: DecodeRequest) -> dict:
    result = await asyncio.to_thread(
        perform_decoding, req.fasta_data, req.alphabet
    )
    return {
        "decoded_bytes": base64.b64encode(result.decoded_bytes).decode("utf-8"),
        "status_message": result.status_message,
        "fec_info": result.fec_info,
    }
