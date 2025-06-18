from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI(title="GeneCoder Web")

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

index_path = static_dir / "index.html"

@app.get("/", response_class=HTMLResponse)  # type: ignore[misc]
async def index() -> str:
    return index_path.read_text(encoding="utf-8")
