import json
import hashlib
from pathlib import Path
from tests.test_cli import run_cli_command
import yaml


def test_bundle_run(tmp_path: Path) -> None:
    input_file = tmp_path / "message.txt"
    input_file.write_text("hello bundle")

    config = {
        "encode": {"input_files": [str(input_file)], "method": "base4_direct"},
        "decode": {"method": "base4_direct"},
    }
    cfg_path = tmp_path / "bundle.yaml"
    cfg_path.write_text(yaml.safe_dump(config))

    cache_dir = tmp_path / "runs"
    result = run_cli_command(["bundle", "run", str(cfg_path), "--cache-dir", str(cache_dir)])
    assert result.returncode == 0, result.stderr

    cfg_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    output_root = cache_dir / cfg_hash
    assert output_root.exists()
    run_dirs = list(output_root.iterdir())
    assert run_dirs, "timestamp directory not created"
    run_dir = run_dirs[0]
    encoded = run_dir / "encoded" / "message.txt.fasta"
    decoded = run_dir / "decoded" / "message.txt_decoded.bin"
    assert encoded.exists()
    assert decoded.exists()
