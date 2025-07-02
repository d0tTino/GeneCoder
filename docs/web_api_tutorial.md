# Web API Tutorial

GeneCoder includes a minimal FastAPI server for web access.

## Starting the server

```bash
uvicorn web.main:app --reload
```

Open <http://127.0.0.1:8000> to view the landing page.

The React helix viewer is available at `/helix`. It accepts optional query
parameters used by `show_helix_ui` such as `seq`, `animate`, `zoom`, `gc`,
`runs`, `pulse`, `pulse_speed` and `colors`. The landing page includes an IFrame
that loads this viewer.

Set the `GENECODER_SIM_SEED` environment variable to an integer to get
reproducible results when API endpoints invoke error simulations.

## Calling the API

```
GET /static/index.html
```

You can add your own endpoints to expose encoding and decoding features.

The server enables [CORS](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
so that browser-based clients on other origins can call the API. Set
`GENECODER_CORS_ORIGINS` to a comma-separated list of allowed origins (default
`*`). Write endpoints also use a bearer token for authentication. Set
`GENECODER_API_TOKEN` before starting the server to supply your own token. If the
variable is unset, a random token is generated at startup and printed to the
console.

```bash
export GENECODER_API_TOKEN=secret
uvicorn web.main:app --reload
```

Include the token when calling `/encode` or `/decode`:

```http
Authorization: Bearer secret
```

## Example Encode/Decode Requests

The server exposes `/encode` and `/decode` POST endpoints. Payloads are JSON:

```json
POST /encode
{
  "data": "SGVsbG8=",
  "options": {"method": "Base-4 Direct"}
}
```

The response contains a FASTA string that can be fed back to `/decode`:

```json
POST /decode
{
  "fasta_data": "<FASTA from /encode>"
}
```

Decoded bytes are returned as a base64 string.

## Sequence Analysis

The `/analyze` endpoint returns [GC content](glossary.md#gc-content) and
[homopolymer](glossary.md#homopolymer) statistics for a
FASTA sequence.

```json
POST /analyze
{
  "fasta_data": ">seq\nACGTACGT\n"
}
```

The JSON response includes the sequence length,
[GC content](glossary.md#gc-content) and the longest
[homopolymer](glossary.md#homopolymer) run.

## Generating Reports

Use `/report` to convert an encoding or decoding result into Markdown or HTML
with helpers from `genecoder.report`.

```json
POST /report
{
  "type": "encode",
  "format": "html",
  "data": {"fasta": ">seq\nACGT\n", "encoded_dna": "ACGT", "metrics": {"gc": 0.5}, "info_messages": []}
}
```

The response contains the rendered report as a string.

## Chunk Upload/Download

Large files can be transferred in pieces using `/upload-chunk` and
`/download-chunk`. Chunks are tracked with the same manifest format as the
streaming helpers.

```python
import base64, httpx

chunk = b"hello"
payload = {"file_id": "example", "offset": 0, "data": base64.b64encode(chunk).decode()}
httpx.post("http://localhost:8000/upload-chunk", json=payload)

r = httpx.get(
    "http://localhost:8000/download-chunk",
    params={"file_id": "example", "offset": 0},
)
data = base64.b64decode(r.json()["data"])
```
