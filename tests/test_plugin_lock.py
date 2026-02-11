import json

import genecoder.plugin_manager as plugins
from genecoder.plugin_runtime.installer import PLUGIN_LOCK


def test_generate_plugin_lock_is_deterministic() -> None:
    PLUGIN_LOCK.clear()
    PLUGIN_LOCK.extend(
        [
            {
                "name": "zeta",
                "version": "2.0",
                "source": "https://example.com/zeta.whl",
                "checksum": "aa",
                "signature": "sig-z",
            },
            {
                "name": "alpha",
                "version": "1.0",
                "source": "https://example.com/alpha.whl",
                "checksum": "bb",
                "signature": "sig-a",
            },
        ]
    )

    rendered = plugins.generate_plugin_lock()
    payload = json.loads(rendered)
    assert [entry["name"] for entry in payload["plugins"]] == ["alpha", "zeta"]
    assert payload["plugins"][0].keys() == {
        "name",
        "version",
        "source",
        "checksum",
        "signature",
    }
