# Helix Frontend

The 3D helix viewer lives in `web/helix-ui`. It is a single-page React
application that uses Three.js for rendering. Overlays indicate
[GC content](glossary.md#gc-content) and
[homopolymer](glossary.md#homopolymer) runs while the helix itself can be
colourised and animated.

The frontend now uses [Vite](https://vitejs.dev/) for development and builds.
To explore the viewer without running the whole backend simply open the built
`dist/index.html` in a browser or start a local HTTP server:

```bash
python -m http.server --directory web/helix-ui/dist 8001
```

## Building the React App

Install the Node dependencies once and run the build:

```bash
cd web/helix-ui
npm install
npm run build
```

The build output appears in `web/helix-ui/dist`. The Flet GUI and FastAPI web
app load this directory via a WebView/IFrame so changes are reflected after
rebuilding.

### Query Parameters

The viewer accepts several query parameters which are also exposed by
`show_helix_ui`:

- `seq` – DNA sequence to visualize.
- `animate` – `true` or `false` to spin the helix.
- `zoom` – numeric zoom factor.
- `gc` – `true`/`false` to show the GC-content overlay.
- `runs` – `true`/`false` to highlight homopolymers.
- `gc_bars` – `true`/`false` to draw GC-content bars.
- `run_bars` – `true`/`false` to draw homopolymer bars.
- `gauge` – `true`/`false` to display overall GC percentage gauges.
- `flash` – `true`/`false` to show error flashes.
- `colors` – comma-separated `base:#hex` pairs, for example
  `A:#ff0000,G:#00ff00`.
- `pulse` – `true`/`false` to enable progress pulses.
- `pulse_speed` – numeric speed multiplier for the pulses.
- `fps` – numeric frames-per-second limit for animation.

Combine these parameters in the page URL or when calling `show_helix_ui`.

Example enabling pulses:

```python
from genecoder.helix_view import show_helix_ui
webview = show_helix_ui("ACGT", pulse=True, pulse_speed=3.0)
```

Set `fps` to cap the frame rate if the animation uses too much CPU:

```python
webview = show_helix_ui("ACGT", fps=30)
```

Disable the GC gauge and show flashing error hints:

```python
webview = show_helix_ui("ACGT", show_gauge=False, flash_errors=True)
```

Enable GC-content and homopolymer bars only:

```python
webview = show_helix_ui(
    "ACGT",
    show_gc_bars=True,
    show_run_bars=True,
    show_gc=False,
    show_runs=False,
)
```
