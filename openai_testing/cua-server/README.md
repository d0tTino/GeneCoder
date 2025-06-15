# CUA Server

![OpenAI API](https://img.shields.io/badge/Powered_by-OpenAI_API-orange)

A Node.js service that interfaces with the OpenAI CUA model and exposes a Socket.IO WebSocket API used by the frontend.

## Setup

1. Copy the example environment file and add your OpenAI key:
   ```bash
   cp .env.example .env.development
   # edit .env.development
   ```
2. Install dependencies and launch the server:
   ```bash
   npm install
   npx playwright install
   npm run dev   # or npm start
   ```
   The server listens on port `8000` by default. Set `SOCKET_PORT` to change it.

### Environment Variables

- `OPENAI_API_KEY` – required for calls to the CUA model.
- `SOCKET_PORT` (optional) – WebSocket port (default `8000`).
- `CORS_ORIGIN` (optional) – allowed CORS origin for incoming connections.
