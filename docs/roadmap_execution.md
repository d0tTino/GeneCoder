<!-- GENERATED FILE: derived from docs/strategy_model.yaml; edit docs/strategy_model.yaml and rerun `python scripts/generate_strategy_artifacts.py --write`. -->

# Roadmap Execution

This execution checklist is generated from the canonical strategy model.

<!-- strategy:execution:start -->
## Execution summary (generated)

> Source of truth: `docs/strategy_model.yaml`
> Validation provenance: `docs/strategy_validation.json`
> last_validated_commit: `cf5265a1d80442ce761d9f8a9218181c8acde3f7`
> generated_at: `2026-03-24T15:29:37Z`
> generator_version: `1.0.0`

### Phase execution focus

- **Phase 1 — Foundation sustainment**: Stabilize shipped bundles, manifests, and dashboard compatibility.
- **Phase 2 — Robust encoding pipeline**: Increase simulator profile coverage without violating runtime budgets.
- **Phase 3 — Simulation and analysis**: Enforce BER, throughput, and category-level CI guardrails.
- **Phase 4 — Ecosystem and automation**: Keep registry publication and execution policy checks continuously green.

### KPI gate checklist

#### Phase 1 -> Phase 2
- Weekly usage (oligos_per_week): **>= 1,000 simulated oligos/week for 4 consecutive ISO weeks**

#### Phase 2 -> Phase 3
- Deterministic reproducibility stability: **100% deterministic seed/profile checks for 2 consecutive weeks**
- Throughput floor: **>= 2.0 MB/s Base-4 encode throughput with BER observed at baseline 0.0**

#### Phase 3 -> Phase 4
- BER baseline quality: **<= 0.01 BER on baseline profile/seed**
- Suite category health: **Green CI across CLI/API, pipeline/simulation, and plugins/security suites**

#### Phase 4 release gate
- Plugin policy compliance: **100% pass on plugin spec/security checks before publication**
<!-- strategy:execution:end -->
