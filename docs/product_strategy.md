# Product Strategy

> last_validated_commit: `4eb89f0cde3b7d75fcaf8311634be19ec56b90f0`

## Phase definitions

| Phase | Name | Objective |
| --- | --- | --- |
| 1 | Foundation sustainment | Keep MVP workflows reliable and reproducible. |
| 2 | Robust encoding pipeline | Expand profile/codec breadth while preserving determinism. |
| 3 | Simulation and analysis | Scale benchmark quality and cross-suite confidence. |
| 4 | Ecosystem and automation | Harden plugin governance and operational automation. |

## Feature capability statuses

| Capability | Status | Phase | Owner modules |
| --- | --- | --- | --- |
| CLI bundle presets for end-to-end pipelines | `implemented` | 1 | `src/genecoder/cli/bundle.py`<br>`src/genecoder/pipeline.py` |
| Illumina simulation with profile-resolved errors | `implemented` | 1 | `src/genecoder/simulators/illumina/channel.py`<br>`src/genecoder/simulators/illumina/profiles.py` |
| Nanopore simulation with context-aware profile controls | `implemented` | 1 | `src/genecoder/simulators/nanopore.py`<br>`src/genecoder/simulators/nanopore_profiles.py` |
| Deterministic seed/profile reproducibility governance | `partial` | 2 | `src/genecoder/pipeline.py`<br>`src/genecoder/cli/cli.py` |
| Standardized benchmark depth and parity validation | `partial` | 3 | `benchmarks/throughput.py`<br>`benchmarks/error_rate.py` |
| Plugin registry policy/security automation | `partial` | 4 | `src/genecoder/plugin_manager.py`<br>`src/genecoder/plugin_runtime/registry.py` |

## Deployment posture flags

| Flag | Value |
| --- | --- |
| `cloud_enabled` | `False` |
| `cloud_worker_enabled` | `False` |
| `local_execution_only` | `True` |
