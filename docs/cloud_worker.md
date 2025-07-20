# Cloud Worker Docker Setup

GeneCoder includes a lightweight worker that exposes a REST API for running bundles remotely. A prebuilt Docker image makes deployment easy.

## Running the Container

Pull and start the worker image while exposing port `8000`:

```bash
docker run -p 8000:8000 \
  -e GENECODER_API_TOKEN=TOKEN \
  -e GENECODER_JOB_DIR=/data/jobs \
  ghcr.io/d0ttino/genecoder python -m genecoder.cloud.worker
```

Replace `TOKEN` with a secret value. The `GENECODER_JOB_DIR` variable controls where uploaded archives and status files are stored (defaults to `worker_jobs`).

## Environment Variables

- `GENECODER_API_TOKEN` – bearer token required for all requests.
- `GENECODER_JOB_DIR` – optional path for job archives.
- `GENECODER_DATA_DIR` – directory for cached profiles and other data.

## Authentication

The worker uses HTTP bearer authentication. Clients must include the token in the `Authorization` header. The CLI automatically adds this header when you run:

```bash
genecoder cloud submit bundle.yaml --server http://localhost:8000 --token TOKEN
```

