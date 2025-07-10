# Usage Metrics

GeneCoder records basic usage statistics in a `metrics.json` file located in `~/.genecoder/` by default. The following counters are tracked:

- `encode_runs` – times the `encode` command has been executed.
- `bundle_runs` – number of `bundle run` workflows executed.
- `oligos_simulated` – total sequences processed by channel simulations.
- `oligos_simulated_ts` – timestamps of each simulated sequence used for weekly
  aggregation.
- `oligos_per_week` – aggregated counts of simulated sequences per ISO week.

GeneCoder's north-star goal is to accelerate DNA storage research by enabling more oligos to be simulated each week. The `oligos_per_week` metric aggregates `oligos_simulated_ts` into ISO weeks, providing a clear view of weekly usage trends.


Display these values with `genecoder stats` or via the `/metrics` web API.
Weekly counts appear under `oligos_per_week`.

Example CLI output:

```bash
$ genecoder stats
encode_runs: 3
bundle_runs: 1
oligos_simulated: 5
oligos_per_week: {"2024-W01": 2, "2024-W02": 3}
```

The `/metrics` endpoint returns the same information:

```bash
$ curl http://localhost:8000/metrics
{
  "encode_runs": 3,
  "bundle_runs": 1,
  "oligos_simulated": 5,
  "oligos_per_week": {"2024-W01": 2, "2024-W02": 3}
}
```
## Migration notes

Version 0.1.1 replaces the previous module-level helpers with a `Metrics` manager
found in `genecoder.metrics`. The legacy `increment` and `get_metrics` functions
remain as thin wrappers around this instance.
