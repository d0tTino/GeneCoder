from genecoder.pipeline import SequencePipeline


def test_sequence_pipeline_basic() -> None:
    pipeline = SequencePipeline([lambda s: s + "A", lambda s: s + "B"])
    assert pipeline.run("X") == "XAB"


def test_sequence_pipeline_parallel() -> None:
    pipeline = SequencePipeline([str.lower])
    seqs = ["A", "B", "C"]
    out = pipeline.run_batch(seqs, parallel=True, workers=2)
    assert out == ["a", "b", "c"]

