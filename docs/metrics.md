# Usage Metrics

GeneCoder records usage statistics into run-scoped artifact files. For pipeline and bundle workflows, keep `metrics.json` and `metrics.kpi.json` next to each run output directory (for example `artifacts/runs/<run-id>/`). The following counters are tracked:

- `encode_runs` – times the `encode` command has been executed.
- `bundle_runs` – number of `bundle run` workflows executed.
- `oligos_simulated` – total sequences processed by channel simulations.
- `oligos_simulated_ts` – timestamps of each simulated sequence used for weekly
  aggregation.
- `oligos_per_week` – aggregated counts of simulated sequences per ISO week.

Pass `--metrics-path /path/to/run/metrics.json` to `genecli bundle run` or
`genecli pipeline` so the metrics and KPI evidence live with each run's outputs.
`genecli pipeline` always emits a sibling `metrics.kpi.json` artifact with a
machine-readable KPI bundle contract.

GeneCoder's north-star goal is to accelerate DNA storage research by enabling more oligos to be simulated each week. The `oligos_per_week` metric aggregates `oligos_simulated_ts` into ISO weeks, providing a clear view of weekly usage trends.


Display these values with `genecli stats` or via the `/metrics` web API.
Weekly counts appear under `oligos_per_week`.

Example CLI output:

```bash
$ genecli stats
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

## Simulation metric notes

Simulation outputs such as `metrics.json` also include per-window distribution
data. The `gc_distribution` entry records the GC fraction of each 50 base pair
window as a value between 0 and 1. Visual dashboards multiply these values by
100 to present min/mean/max summaries and line charts in percentage units.


## Scenario cost analysis

Bundle manifests can include a `simulate.cost_model` block to estimate economics for each run:

- `synthesis.usd_per_nt`
- `sequencing.usd_per_read`
- `redundancy.baseline_coverage`

When present, GeneCoder emits these derived metrics into decoded metrics/manifests:

- `cost_per_recovered_bit`
- `reads_per_successful_decode`
- `redundancy_cost_ratio`

Use `genecli stats bundle --runs <cache_dir>` to aggregate scenario outputs across runs.
