# Frontend UI

![NextJS](https://img.shields.io/badge/Built_with-NextJS-blue)

This Next.js application provides the web interface for the Testing Agent demo. It allows you to define test cases, sends them to the CUA server and displays messages from the CUA model in the UI.

## Setup

1. Copy the example environment file and add your OpenAI key:
   ```bash
   cp .env.example .env.development
   # edit .env.development
   ```
2. Install dependencies and start the dev server:
   ```bash
   npm install
   npm run dev
   ```
   The app will be running at [http://localhost:3000](http://localhost:3000).

Make sure the CUA server is running (see [cua-server/README.md](../cua-server/README.md)) and, for demo purposes, the sample app ([sample-test-app/README.md](../sample-test-app/README.md)).
