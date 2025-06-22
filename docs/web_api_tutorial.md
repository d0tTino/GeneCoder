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
