# Helix UI

This directory contains the React-based interfaces used by the GeneCoder web server.

![Enhanced dashboard](src/assets/dashboard_enhanced.svg)

The redesigned dashboard surfaces multi-oligo dropout, coverage heatmaps and oligo inspectors to match the new pipeline flow.

## Building

Install Node dependencies and run the build script:

```bash
npm install
npm run build
```

The compiled assets will be placed in the `dist` folder. During development you can run `npm run dev` to launch a hot-reload server.

## Dashboard & Scoreboard

The React dashboard (`dashboard.html`) and scoreboard (`scoreboard.html`) share the same build. After running `npm run build` open `dist/dashboard.html` to explore the enhanced charts or `dist/scoreboard.html` to submit challenge scores. When previewing alongside the Python documentation, run `mkdocs serve` in another terminal so content changes are reflected in both places.
