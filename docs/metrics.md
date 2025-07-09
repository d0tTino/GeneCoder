# Usage Metrics

GeneCoder records basic usage statistics in a `metrics.json` file located in `~/.genecoder/` by default. The following counters are tracked:

- `encode_runs` – times the `encode` command has been executed.
- `bundle_runs` – number of `bundle run` workflows executed.
- `oligos_simulated` – total sequences processed by channel simulations.

Display these values with `genecoder stats` or via the `/metrics` web API endpoint. Set the `GENECODER_METRICS_PATH` environment variable to use a custom file location.
