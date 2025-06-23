# Web API Tutorial

GeneCoder includes a minimal FastAPI server for web access.

## Starting the server

```bash
uvicorn web.main:app --reload
```

Open <http://127.0.0.1:8000> to view the landing page.

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
