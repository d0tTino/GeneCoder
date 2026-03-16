from __future__ import annotations

from pathlib import Path

import pytest

from genecoder.pipeline_service_contract import (
    PipelineJobRequest,
    bundle_config_to_job_request,
    planned_execution_graph,
)

yaml = pytest.importorskip("yaml")


def test_bundle_config_maps_to_pipeline_contract_gold() -> None:
    config_path = Path("configs/gold.yaml")
    bundle_cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    req = bundle_config_to_job_request(
        bundle_cfg,
        input_path="tests/data/vertical_slice.txt",
        output_path="tmp/decoded.bin",
    )

    assert req.codec == "gc_balanced"
    assert req.fec == "reed_solomon"
    assert req.channel == "insilicoseq"
    assert req.profile_name == "miseq"
    assert req.constraints["gc_min"] == pytest.approx(0.4)
    assert req.constraints["gc_max"] == pytest.approx(0.6)


def test_pipeline_contract_validates_and_builds_graph() -> None:
    req = PipelineJobRequest.from_mapping(
        {
            "codec": "base4_direct",
            "input_path": "in.bin",
            "output_path": "out.bin",
            "channel": "illumina",
            "seeds": {"global_seed": 3},
            "matrix_axes": {"coverage": [5, 10]},
        }
    )

    graph = planned_execution_graph(req)
    node_ids = [node["id"] for node in graph["nodes"]]
    assert node_ids == ["encode", "simulate", "decode", "artifacts"]
    assert graph["edges"][0] == {"from": "encode", "to": "simulate"}


def test_pipeline_contract_requires_core_fields() -> None:
    with pytest.raises(ValueError, match="codec is required"):
        PipelineJobRequest.from_mapping({"input_path": "in", "output_path": "out"})
