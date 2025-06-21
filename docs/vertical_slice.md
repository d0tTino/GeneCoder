# Vertical Slice Walkthrough

This guide demonstrates a minimal end-to-end run of GeneCoder.

## Prerequisites

- **Python 3.10+**
- **Poetry** for dependency management

## Environment Setup

```bash
git clone https://github.com/d0tTino/GeneCoder.git
cd GeneCoder
poetry install --with gui,web --no-interaction
```

## CLI Smoke Test

Ensure the command line interface is available and the test suite passes:

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
