import pytest
import genecoder.plugin_manager as plugins

pytest.importorskip("yaml")


def test_invalid_yaml_raises_error():
    with pytest.raises(plugins.yaml.YAMLError):
        plugins.yaml.safe_load("bad: [yaml")

