from __future__ import annotations

import json
import os
import sys
import re
import types
from pathlib import Path

from tests.test_cli import run_cli_command


def test_channel_demo_config(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parent.parent
    config_template = repo_root / "configs" / "channel_demo.yaml"
    config_text = config_template.read_text(encoding="utf-8")
    min_length_match = re.search(r"min_length:\s*(\d+)", config_text)
    max_length_match = re.search(r"max_length:\s*(\d+)", config_text)
    max_homopolymer_match = re.search(r"max_homopolymer:\s*(\d+)", config_text)
    read_length_match = re.search(r"read_length:\s*(\d+)", config_text)
    sub_rate_match = re.search(r"substitution_rate:\s*([0-9.eE+-]+)", config_text)
    ins_rate_match = re.search(r"insertion_rate:\s*([0-9.eE+-]+)", config_text)
    del_rate_match = re.search(r"deletion_rate:\s*([0-9.eE+-]+)", config_text)
    coverage_match = re.search(r"coverage:\s*([0-9.eE+-]+)", config_text)
    parallel_match = re.search(r"parallel:\s*(true|false)", config_text)
    workers_match = re.search(r"workers:\s*(null|\d+)", config_text)
    process_pool_match = re.search(r"use_process_pool:\s*(true|false)", config_text)
    mpi_match = re.search(r"use_mpi:\s*(true|false)", config_text)
    assert (
        min_length_match
        and max_length_match
        and max_homopolymer_match
        and read_length_match
        and sub_rate_match
        and ins_rate_match
        and del_rate_match
        and coverage_match
        and parallel_match
        and workers_match
        and process_pool_match
        and mpi_match
    ), "Channel demo YAML is missing expected fields"
    min_length = int(min_length_match.group(1))
    max_length = int(max_length_match.group(1))
    max_homopolymer = int(max_homopolymer_match.group(1))
    read_length = int(read_length_match.group(1))
    substitution_rate = float(sub_rate_match.group(1))
    insertion_rate = float(ins_rate_match.group(1))
    deletion_rate = float(del_rate_match.group(1))
    coverage = float(coverage_match.group(1))
    parallel = parallel_match.group(1).lower() == "true"
    workers_raw = workers_match.group(1)
    workers = None if workers_raw.lower() == "null" else int(workers_raw)
    use_process_pool = process_pool_match.group(1).lower() == "true"
    use_mpi = mpi_match.group(1).lower() == "true"

    input_path = tmp_path / "input.fasta"
    input_path.write_text(">seq1\nACGTACGTACGTACGTACGTACGTAC\n", encoding="utf-8"
    )

    output_path = tmp_path / "output.fasta"

    config_path = tmp_path / "channel_demo.yaml"
    config_data = {
        "input": input_path.as_posix(),
        "output": output_path.as_posix(),
        "synthesis": {
            "min_length": min_length,
            "max_length": max_length,
            "max_homopolymer": max_homopolymer,
        },
        "simulators": [
            {
                "name": "illumina",
                "substitution_rate": substitution_rate,
                "insertion_rate": insertion_rate,
                "deletion_rate": deletion_rate,
                "coverage": coverage,
                "read_length": read_length,
            }
        ],
        "pipeline": {
            "parallel": parallel,
            "workers": workers,
            "use_process_pool": use_process_pool,
            "use_mpi": use_mpi,
        },
    }
    config_path.write_text(json.dumps(config_data, indent=2), encoding="utf-8")

    env = os.environ.copy()
    env["GENECODER_SIM_SEED"] = "123"
    src_path = repo_root / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")

    json_yaml = types.ModuleType("yaml")

    def _safe_load(source: object) -> dict[str, object]:
        if hasattr(source, "read"):
            text = source.read()
        else:
            text = str(source)
        text = text.strip()
        if not text:
            return {}
        return json.loads(text)

    def _safe_dump(data: object) -> str:
        return json.dumps(data)

    class _YamlError(Exception):
        pass

    json_yaml.safe_load = _safe_load  # type: ignore[attr-defined]
    json_yaml.safe_dump = _safe_dump  # type: ignore[attr-defined]
    json_yaml.YAMLError = _YamlError  # type: ignore[attr-defined]

    original_yaml = sys.modules.get("yaml")
    sys.modules["yaml"] = json_yaml
    try:
        result = run_cli_command(["channel", "run", str(config_path)], env=env)
    finally:
        if original_yaml is not None:
            sys.modules["yaml"] = original_yaml
        else:
            sys.modules.pop("yaml", None)

    assert result.returncode == 0, result.stderr
    assert output_path.exists()

    manifest_path = output_path.with_suffix("")
    manifest_path = manifest_path.with_name(manifest_path.name + ".manifest.json")
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    constraints = manifest.get("constraints", {})
    assert constraints.get("min_length") == min_length
    assert constraints.get("max_length") == max_length
    assert constraints.get("max_homopolymer") == max_homopolymer

    stages = manifest.get("stages")
    assert isinstance(stages, list) and stages
    illumina_stage = next((stage for stage in stages if stage.get("name") == "illumina"), None)
    assert illumina_stage is not None
    parameters = illumina_stage.get("parameters")
    assert isinstance(parameters, dict)
    assert parameters.get("read_length") == read_length

