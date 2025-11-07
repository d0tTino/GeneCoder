from __future__ import annotations

from pathlib import Path

import pytest

from tests.test_cli import run_cli_command

yaml = pytest.importorskip("yaml")
if yaml.safe_load("test: value") == {}:
    pytest.skip("PyYAML required for bundle preset test", allow_module_level=True)


def test_bundle_gold_config(tmp_path: Path) -> None:
    cache_dir = tmp_path / "runs"
    env = {"GENECODER_SIM_SEED": "12345"}

    result = run_cli_command(
        ["bundle", "run", "configs/gold.yaml", "--cache-dir", str(cache_dir)],
        env=env,
    )

    assert result.returncode == 0, result.stderr

    hash_dirs = sorted(cache_dir.iterdir())
    assert len(hash_dirs) == 1, "unexpected number of config hash directories"
    run_dirs = sorted(hash_dirs[0].iterdir())
    assert run_dirs, "no timestamped run directory created"
    run_dir = run_dirs[-1]

    encoded_dir = run_dir / "encoded"
    simulated_dir = run_dir / "simulated"
    decoded_dir = run_dir / "decoded"

    encoded_manifest = encoded_dir / "vertical_slice.txt.manifest.json"
    simulated_manifest = simulated_dir / "vertical_slice.txt.manifest.json"

    assert encoded_manifest.exists(), "encoded manifest missing"
    assert simulated_manifest.exists(), "simulated manifest missing"

    decoded_output = decoded_dir / "vertical_slice.txt_decoded.bin"
    assert decoded_output.exists(), "decoded output missing"

    expected_payload = Path("tests/data/vertical_slice.txt").read_bytes()
    assert decoded_output.read_bytes() == expected_payload

    # Ensure core outputs remain available for downstream tooling.
    assert (encoded_dir / "vertical_slice.txt.fasta").exists()
    assert (simulated_dir / "vertical_slice.txt.fasta").exists()
    assert (run_dir / "sequence_batches.json").exists()
