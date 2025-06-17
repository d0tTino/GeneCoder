from genecoder.manifest import generate_manifest
from genecoder.cli import EncodingOptions


def test_generate_manifest_basic() -> None:
    opts = EncodingOptions(
        method="base4_direct",
        add_parity=False,
        k_value=7,
        parity_rule="PR",
        fec=None,
        gc_min=0.45,
        gc_max=0.55,
        max_homopolymer=3,
    )
    metrics = {"dna_length": 10}
    manifest = generate_manifest("file.txt", opts, metrics)
    assert manifest["file"] == "file.txt"
    assert manifest["encoding_parameters"]["method"] == "base4_direct"
    assert manifest["metrics"]["dna_length"] == 10
