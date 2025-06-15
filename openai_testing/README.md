# OpenAI Testing Environment

This directory contains the resources from the
[openai-testing-agent-demo](https://github.com/openai/openai-testing-agent-demo)
project.  It includes three applications used to run the demo testing agent:

- **cua-server** – Node service that communicates with the OpenAI CUA model and
  controls Playwright.
- **frontend** – Next.js interface for configuring and watching tests.
- **sample-test-app** – Example e‑commerce site used by the agent.

## Prerequisites

- [Node.js](https://nodejs.org) with `npm` available in your `PATH`.
- An `OPENAI_API_KEY` environment variable with access to the CUA model.

## Running the demo

Install dependencies from the root of `openai_testing` and start all three
applications:

```bash
cd openai_testing
npm install
npx playwright install  # one-time browser setup
npm run dev
```

This starts the sample app on http://localhost:3005, the frontend on
http://localhost:3000 and the CUA server on ws://localhost:8080. Open the
frontend URL to watch the agent run tests.

A convenience script is provided to start the Flet GUI from this repository and
connect to the running CUA server:

```bash
make openai-testing
```


