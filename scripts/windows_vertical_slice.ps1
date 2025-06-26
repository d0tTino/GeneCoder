# PowerShell script for the GeneCoder vertical slice demo
# This mirrors the steps outlined in docs/vertical_slice.md
# Run from the repository root with:
#   powershell -ExecutionPolicy Bypass -File scripts/windows_vertical_slice.ps1

$ErrorActionPreference = 'Stop'

Write-Host "Installing dependencies with optional extras..."
poetry install --with gui,web,dnaformer --no-interaction

Write-Host "Running CLI smoke test..."
genecoder --version
poetry run pytest -q

Write-Host "Launching the Flet GUI..."
python -m genecoder.flet_app

Write-Host "Starting the FastAPI server..."
poetry run uvicorn web.main:app --reload
