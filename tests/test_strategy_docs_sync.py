from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import yaml


def _load_renderer_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "render_strategy_docs.py"
    spec = spec_from_file_location("render_strategy_docs", script_path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rendered_docs_include_last_validated_commit_and_posture_flags():
    renderer = _load_renderer_module()
    model_path = Path(__file__).resolve().parents[1] / "docs" / "strategy_model.yaml"
    model = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    rendered = renderer.render_docs(model)

    for content in rendered.values():
        assert f"last_validated_commit: `{model['last_validated_commit']}`" in content

    cloud_doc = rendered[renderer.OUTPUT_DOCS["cloud"]]
    assert "`cloud_enabled`: `False`" in cloud_doc
    assert "`cloud_worker_enabled`: `False`" in cloud_doc
    assert "`local_execution_only`: `True`" in cloud_doc
