# Offline Usage

GeneCoder avoids network access by default and supports fully air‑gapped deployments.
This guide shows how to configure offline mode, provide local profiles and
manage the optional plugin registry.

## Environment Flags

Most CLI commands accept `--offline` to disable all network operations.
The same behaviour can be enabled globally by setting `GENECODER_OFFLINE=1`.

The web UI uses a local Pyodide bundle by default. Place the Pyodide
distribution under `web/static/pyodide/` so it is served from
`/static/pyodide/pyodide.js`. To point the UI at a different (possibly remote)
bundle, set `GENECODER_PYODIDE_SRC` to the desired `pyodide.js` URL.

## Profile Paths

Sequencing simulators may download profile files the first time they run.
Set `GENECODER_PROFILE_DIR` to a directory containing pre‑downloaded profiles
so runs succeed without contacting the network. Cached data normally lives
under `~/.genecoder/data`; override this location with `GENECODER_DATA_DIR`.

## Plugin Registry Opt‑In

GeneCoder only loads plugins already installed in the environment. To install
additional packages from a registry provide `GENECODER_PLUGIN_REGISTRY_URL`
and opt in explicitly:

```bash
genecli plugin install-registry --allow-registry [--offline]
```

`--allow-registry` confirms you trust the registry source. When the registry and
wheels are available locally add `--offline` to prevent any network access. Set
`GENECODER_PLUGIN_CATALOG_URL` to point plugin management commands at a JSON or
YAML catalog, or leave both variables empty to disable remote lookups entirely.
