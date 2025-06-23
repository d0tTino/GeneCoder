# Web API Tutorial

GeneCoder includes a minimal FastAPI server for web access.

## Starting the server

```bash
uvicorn web.main:app --reload
```

Open <http://127.0.0.1:8000> to view the landing page.

Set the `GENECODER_SIM_SEED` environment variable to an integer to get
reproducible results when API endpoints invoke error simulations.

## Calling the API

```
GET /static/index.html
```

You can add your own endpoints to expose encoding and decoding features.
