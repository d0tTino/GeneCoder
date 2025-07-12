# Deployment Guide

This guide summarizes how to build the React dashboard, start a cloud worker with Docker and submit jobs via the CLI.

## Build the Dashboard

The web interface lives in `web/helix-ui` and uses React and Vite. Compile the static assets once before running the backend:

```bash
cd web/helix-ui
npm install
npm run build
```

The generated files are placed in `web/helix-ui/dist`. The FastAPI server automatically serves this folder when available.

## Launch the Cloud Worker

`genecoder.cloud.worker` provides a minimal REST API for running bundles remotely. Start it inside a container:

```bash
docker run -p 8000:8000 -e GENECODER_API_TOKEN=TOKEN \
    ghcr.io/d0ttino/genecoder python -m genecoder.cloud.worker
```

Replace `TOKEN` with a secret value. The CLI must use the same token when submitting jobs.

## Submit a Job

Packages and uploads are handled by `genecoder cloud submit`:

```bash
genecoder cloud submit bundle.yaml --server http://localhost:8000 --token TOKEN
```

The command archives the bundle and any input files then posts it to `/jobs` on the running worker. The returned job identifier is printed to the console.
