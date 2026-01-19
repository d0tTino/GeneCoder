# Local Pyodide Bundle

This directory should contain the Pyodide distribution that the web UI loads by
default. Copy the *full* `pyodide` release contents into this directory so the
files are served at `/static/pyodide/`.

## Build / Copy Instructions

1. Download the Pyodide release assets (example below uses v0.24.0):

   ```bash
   mkdir -p /tmp/pyodide
   curl -L https://cdn.jsdelivr.net/pyodide/v0.24.0/full/ -o /tmp/pyodide/index.html
   curl -L https://cdn.jsdelivr.net/pyodide/v0.24.0/full/pyodide.js -o /tmp/pyodide/pyodide.js
   curl -L https://cdn.jsdelivr.net/pyodide/v0.24.0/full/pyodide.asm.wasm -o /tmp/pyodide/pyodide.asm.wasm
   curl -L https://cdn.jsdelivr.net/pyodide/v0.24.0/full/pyodide.asm.data -o /tmp/pyodide/pyodide.asm.data
   curl -L https://cdn.jsdelivr.net/pyodide/v0.24.0/full/pyodide_py.tar -o /tmp/pyodide/pyodide_py.tar
   curl -L https://cdn.jsdelivr.net/pyodide/v0.24.0/full/packages.json -o /tmp/pyodide/packages.json
   curl -L https://cdn.jsdelivr.net/pyodide/v0.24.0/full/repodata.json -o /tmp/pyodide/repodata.json
   ```

2. Copy the downloaded files into this directory:

   ```bash
   cp /tmp/pyodide/* /path/to/GeneCoder/web/static/pyodide/
   ```

3. Start the web server normally. The UI will load Pyodide from
   `/static/pyodide/pyodide.js`. Override the default by setting
   `GENECODER_PYODIDE_SRC` to another URL.

> Note: The list above includes the minimum assets needed for the default
> `full` Pyodide build. If you use a different build or version, copy the
> matching files here.
