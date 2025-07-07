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
stdout.
