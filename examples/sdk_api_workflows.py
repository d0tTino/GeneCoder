"""API-level workflow examples for GeneCoder SDK roadmap scenarios."""

from genecoder.sdk import ExperimentRequest, run_experiment, sweep


def single_run() -> None:
    run_experiment(
        ExperimentRequest(
            codec="reverse",
            input_path="input.bin",
            output_path="single.decoded.bin",
            channel="none",
        )
    )


def sweep_run() -> None:
    sweep(
        [
            {
                "codec": "reverse",
                "input_path": "input.bin",
                "output_path": "sweep-a.bin",
                "matrix": {"substitution_rate": [0.0, 0.01, 0.05]},
            },
            {
                "codec": "reverse",
                "input_path": "input.bin",
                "output_path": "sweep-b.bin",
                "matrix": {"coverage": [5, 10]},
            },
        ]
    )


def compare_runs() -> None:
    baseline = run_experiment(
        {
            "codec": "reverse",
            "input_path": "input.bin",
            "output_path": "baseline.bin",
        }
    )
    candidate = run_experiment(
        {
            "codec": "reverse",
            "input_path": "input.bin",
            "output_path": "candidate.bin",
            "profile": {"name": "illumina", "parameters": {"substitution_rate": 0.01}},
        }
    )
    print("baseline throughput", baseline.dashboard_metrics.get("throughput"))
    print("candidate throughput", candidate.dashboard_metrics.get("throughput"))


def bundle_workflow() -> None:
    runs = sweep(
        [
            {
                "codec": "reverse",
                "input_path": "input_a.bin",
                "output_path": "bundle/a.bin",
                "artifacts": {"metrics_path": "bundle/a.run.json"},
            },
            {
                "codec": "reverse",
                "input_path": "input_b.bin",
                "output_path": "bundle/b.bin",
                "artifacts": {"metrics_path": "bundle/b.run.json"},
            },
        ]
    )
    print([run.artifact_paths["metrics"] for run in runs.runs])


if __name__ == "__main__":
    single_run()
