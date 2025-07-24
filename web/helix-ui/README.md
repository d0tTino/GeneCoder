# Helix UI

This directory contains the React-based interfaces used by the GeneCoder web server.

## Building

Install Node dependencies and run the build script:

```bash
npm install
npm run build
```

The compiled assets will be placed in the `dist` folder. During development you can run `npm run dev` to launch a hot-reload server.

## Scoreboard

The React scoreboard page lives in `scoreboard.html` and relies on the `/catalog/challenge` API. After running `npm run build` open `dist/scoreboard.html` directly or visit `/helix-ui/scoreboard.html` while the backend server is running to view and submit challenge scores.
