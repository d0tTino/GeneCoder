# Deployment Guide

This guide summarizes how to build the React dashboard and run the web server locally.
Remote job submission via the old cloud worker has been removed.

## Build the Dashboard

The web interface lives in `web/helix-ui` and uses React and Vite. Compile the static assets once before running the backend:

```bash
cd web/helix-ui
npm install
npm run build
```

The generated files are placed in `web/helix-ui/dist`. The FastAPI server automatically serves this folder when available.

## Run the Web Server

Install the optional `web` extras and start the FastAPI server locally:

```bash
poetry install --with web --no-interaction
uvicorn web.main:app --reload
```

Set `GENECODER_API_TOKEN` to your desired bearer token. When the server is
running it serves the dashboard from `web/helix-ui/dist` at the root URL.

See [mpi.md](mpi.md) for instructions on running channel simulations across multiple nodes using MPI.


## Primary UI Track and Adapter Policy

GeneCoder now maintains a single **primary UI track** for deployments:

- **Primary (fully supported):** `genecli` + React dashboard (`/dashboard` in the FastAPI app).
- **Optional adapters (best-effort support):** Flet desktop UI and Streamlit dashboards.

All UI adapters must call the same headless application contract (`genecoder.app.ui_service.UIService`) for pipeline runs, run comparison, plugin/profile discovery, and artifact load/export. This keeps behavior consistent across transport layers.

For production deployments, use CLI automation and/or the React dashboard as the default operator surface. Optional adapters may lag behind in feature parity and are not part of the strict deployment compatibility guarantee.
