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

The `/analyze` endpoint returns GC content and homopolymer statistics for a
FASTA sequence.

```json
POST /analyze
{
  "fasta_data": ">seq\nACGTACGT\n"
}
```

The JSON response includes the sequence length, GC content and the longest
homopolymer run.

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
