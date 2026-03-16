from genecoder.cost_model import compute_cost_outputs, parse_cost_model_inputs


def test_compute_cost_outputs() -> None:
    inputs = parse_cost_model_inputs(
        {
            "synthesis": {"usd_per_nt": 0.001},
            "sequencing": {"usd_per_read": 0.01},
            "redundancy": {"baseline_coverage": 5},
        }
    )
    outputs = compute_cost_outputs(
        inputs=inputs,
        total_nt=100,
        total_reads=50,
        recovered_bytes=25,
        decode_success_rate=0.5,
    )

    assert outputs.cost_per_recovered_bit > 0
    assert outputs.reads_per_successful_decode == 100
    assert outputs.redundancy_cost_ratio == 10
