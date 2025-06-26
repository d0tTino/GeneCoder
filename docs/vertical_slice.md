# Vertical Slice Walkthrough

This guide demonstrates a minimal end-to-end run of GeneCoder. A convenient
PowerShell script is provided for Windows users to run the demo automatically.

## Prerequisites

- **Python 3.11+**
- GeneCoder uses **Poetry** for dependency management

## Environment Setup

```bash
git clone https://github.com/d0tTino/GeneCoder.git
cd GeneCoder
poetry install --with gui,web,dnaformer --no-interaction
```

### Automated Windows Script

Windows users can run all of the steps below with the provided PowerShell
script. The same `poetry install` command installs the optional GUI and web
extras on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/windows_vertical_slice.ps1
```

The script prints the GeneCoder version, runs the test suite, launches the Flet
GUI and finally starts the FastAPI server. The last lines of output should
include:

```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

Open that address in your browser to confirm the server is reachable.

## CLI Smoke Test

Ensure the command line interface is available and the test suite passes. On
Windows this is run from PowerShell just like on Linux:

```bash
genecoder --version
poetry run pytest -q
```

## Launch the GUI

```bash
python -m genecoder.flet_app
```

## Start the FastAPI Server

```bash
poetry run uvicorn web.main:app --reload
```

Open <http://localhost:8000> in your browser to view the landing page.

This document condenses the key steps from the installation and usage guides into a quick demo.

Contributors may prefer to run these commands inside the provided
**devcontainer** for a ready-to-use environment.
