# Cloud Worker Integration

GeneCoder can submit encode/decode jobs to a remote worker via a simple REST API.
The :class:`genecoder.cloud.CloudClient` provides a minimal wrapper for sending
jobs to a queue exposed by a web service.

```python
from genecoder.cloud import CloudClient

with CloudClient("https://worker:8000", token="TOKEN") as client:
    job = client.submit("bundle", {"archive": "<base64 data>"})
    print(job)
```

## CLI Usage

Bundles can be packaged and uploaded using the `genecoder cloud submit` command:

```bash
genecoder cloud submit bundle.yaml --server https://worker:8000 --token TOKEN
```

The command creates a ZIP archive containing the bundle file and any input files
listed under the `encode.input_files` section. The archive is Base64 encoded and
sent to the remote worker's `/jobs` endpoint. The returned job ID is printed to
stdout and the command waits until the job completes by polling `/jobs/{id}`.

## Running the Worker

The worker application is located at `genecoder.cloud.worker`. It exposes a `/jobs` endpoint that accepts the archive produced by `genecoder cloud submit` and executes the bundle locally.

A convenient way to start the worker is using Docker:

```bash
docker run -p 8000:8000 -e GENECODER_API_TOKEN=TOKEN ghcr.io/d0ttino/genecoder \
    python -m genecoder.cloud.worker
```

Replace `TOKEN` with a secret value and use the same token when submitting jobs.
Uploaded archives are stored under ``GENECODER_JOB_DIR`` (default ``worker_jobs``)
and can be queried via ``GET /jobs/{id}`` to check progress.

## HPC Submission

Jobs can also be dispatched directly to a Slurm cluster. Provide a command that
will be executed on the compute node and optional Slurm parameters:

```python
from genecoder.cloud import CloudClient

with CloudClient("unused") as client:
    jid = client.submit(
        "hpc",
        {
            "command": "genecoder bundle run bundle.yaml --cache-dir runs",
            "job_name": "gc-run",
            "time": "00:30:00",
            "partition": "compute",
        },
    )
    print(jid)
```

Equivalent settings can be expressed in YAML:

```yaml
job:
  type: hpc
  command: genecoder bundle run bundle.yaml --cache-dir runs
  job_name: gc-run
  time: 00:30:00
  partition: compute
```

Use the CLI to submit such a file directly via Slurm:

```bash
genecoder cloud submit --hpc-config job.yaml
```

## Fetching Error Profiles

GeneCoder can download example anonymized error profiles for use with simulators.
Use the CLI to fetch a profile and store it in the local cache:

```bash
genecoder data fetch illumina_profile.json --url https://example.com/profiles
```

Profiles are saved under `~/.genecoder/data` by default. The location can be
customized with the `--cache-dir` option or the `GENECODER_DATA_DIR`
environment variable.
