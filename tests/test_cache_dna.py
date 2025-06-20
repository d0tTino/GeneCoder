import json
from pathlib import Path

from genecoder.cache_dna import write_capsule


def test_write_capsule(tmp_path: Path) -> None:
    path = tmp_path / "capsules" / "capsule.capsule"
    metadata = {"foo": "bar"}
    write_capsule("ACGT", "header", metadata, str(path))

    assert path.exists()
    data = json.loads(path.read_text())
    assert data["version"] == 1
    assert data["header"] == "header"
    assert data["sequence"] == "ACGT"
    assert data["metadata"] == metadata
    assert "created" in data
