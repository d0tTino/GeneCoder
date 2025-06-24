# Helix Frontend

The 3D helix viewer lives in `web/helix-ui`. It is a single-page React
application that uses Three.js for rendering and displays simple overlays for
GC content and homopolymer runs.

To explore the viewer without running the whole backend simply open
`web/helix-ui/index.html` in a browser or start a local HTTP server:

```bash
python -m http.server --directory web/helix-ui 8001
```

During development you can edit `index.html` and reload the page. The Flet GUI
and FastAPI web app load the same file via a WebView/IFrame, so changes are
reflected automatically.
