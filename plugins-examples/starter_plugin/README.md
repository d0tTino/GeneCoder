# Starter Plugin Template

This directory contains a minimal, installable GeneCoder plugin package that
registers a codec via the ``genecoder.plugins`` entry point group. Use it as a
starting point for your own codec or simulator implementations.

## How to adapt the template

1. Update ``PLUGIN_METADATA`` and the class name in
   ``starter_plugin/__init__.py`` to reflect your plugin's identity
   (including setting an approved SPDX ``license`` such as ``MIT``).
2. Replace the example codec logic with your own encode/decode behavior or swap
   the interface to a simulator by following the inline comments in the module.
3. Adjust the entry point name in ``pyproject.toml`` if you change the public
   identifier for the plugin.

## Run locally

Install the example from the repository root:

```bash
python -m pip install ./plugins-examples/starter_plugin
```

Then run a quick encode/decode round trip:

```bash
python - <<'PY'
from genecoder import CODEC_REGISTRY, load_plugins
load_plugins()
codec = CODEC_REGISTRY["starter_template"]
encoded = codec["encode"](b"hello")
print(encoded, codec["decode"](encoded))
PY
```

## Verify discovery with ``genecli``

After installation, ``genecli`` will surface the metadata the plugin exports via
``PLUGIN_METADATA`` when you ask for the plugin catalog:

```bash
genecli plugin list
```

You should see ``starter-template`` in the output. Use the same command to
confirm your own plugin appears once you rename the metadata.
