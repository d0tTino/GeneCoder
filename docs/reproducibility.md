# Reproducibility Guide

Deterministic experiments make it easier to compare codecs, simulators and
pipelines across machines. This guide captures the minimum runtime requirements
for GeneCoder and the knobs you can tune to make channel simulations repeatable.

## Supported Python Versions

GeneCoder targets **Python 3.11 or newer**. The CLI and bundled plugins are
actively tested on CPython 3.11 and 3.12. Earlier versions are unsupported and
will miss typing improvements relied on by the codebase. Install the toolchain
through [Poetry](https://python-poetry.org/) or your preferred virtual
environment manager, but ensure that the interpreter is at least version 3.11.

## Recommended Operating Systems and Hardware

While GeneCoder runs on Linux, macOS and Windows (via WSL2 or the native
installers), the following setups provide the smoothest experience when running
full pipelines:

- **Linux**: Ubuntu 22.04 LTS or Fedora 39 on a 64-bit system.
- **macOS**: Ventura 13 or Sonoma 14 on Apple Silicon or Intel hardware.
- **Windows**: Windows 11 with WSL2 enabled and an Ubuntu 22.04 distribution.

Regardless of platform, plan for:

- **CPU**: 4 physical cores (or better) to parallelize encode and channel steps.
- **Memory**: 16&nbsp;GB RAM to accommodate simultaneous simulator and decoder
  workloads.
- **Storage**: 10&nbsp;GB of free SSD space for Poetry environments, simulator
  caches and manifest artifacts.

These specs match the footprint observed when enabling the optional GUI, web and
FEC extras listed in the quick start section of the README. Lightweight encode
and decode runs will work on smaller systems, but the margin above prevents
unexpected slowdowns or swapping when running multi-oligo experiments.

## Seeding the Simulation RNG

GeneCoder centralizes all pseudo-random number generation through the
`GENECODER_SIM_SEED` environment variable. Export it before invoking any CLI
command to lock in deterministic noise sequences:

```bash
export GENECODER_SIM_SEED=12345
```

The CLI also exposes `--seed` wherever randomness is involved. Passing
`--seed 12345` automatically sets the same environment variable for the duration
of the command, so you can either export it globally or set it per invocation:

```bash
genecli pipeline input.txt decoded.txt --channel illumina --illumina-profile miseq --seed 12345 \
  --metrics-path artifacts/runs/repro-seed/metrics.json
```

Any sub-process launched by the CLI (including bundled simulators) inherits the
seed, ensuring reproducible dropout patterns, coverage distributions and quality
score sampling.

## Pinning Illumina Profiles

Illumina simulations expose named profiles that adjust quality scores, read
lengths and dropout behaviour. To reproduce specific lab presets, explicitly
select the desired profile in your CLI commands or bundle configuration.

### CLI invocations

```bash
# MiSeq-style short reads
GENECODER_SIM_SEED=12345 genecli pipeline \
  examples/pipeline_demo_input.txt decoded_miseq.txt \
  --channel illumina --illumina-profile miseq \
  --metrics-path artifacts/runs/repro-miseq/metrics.json

# NovaSeq high-throughput profile
GENECODER_SIM_SEED=12345 genecli pipeline \
  examples/pipeline_demo_input.txt decoded_novaseq.txt \
  --channel illumina --illumina-profile novaseq \
  --metrics-path artifacts/runs/repro-novaseq/metrics.json
```

### Bundle and pipeline configurations

Add the profile under the `simulate` stage so the bundle executor chooses the
same preset each run:

```yaml
simulate:
  simulators:
    - illumina
  pipeline:
    illumina_profile: miseq_v3
```

Switch `illumina_profile` to `hiseq_high_coverage`, `novaseq_s4`, or any other
registered profile to lock in different quality curves. When combined with a
fixed `GENECODER_SIM_SEED`, MiSeq V3 and NovaSeq S4 simulations yield identical
error statistics across repeated runs, which is ideal for regression testing and
benchmarking new codecs.

## Validating sequencing profile error rates

Both the Nanopore and Illumina simulators now expose helper hooks that emit
aggregate substitution/insertion/deletion counts for a deterministic run. The
pytest suite drives these hooks to ensure the bundled configuration files stay
in sync with the observed behaviour:

- `tests/test_nanopore_context_profile.py` calls
  `genecoder.simulators.nanopore_batch.observe_error_rates` for each profile in
  `configs/nanopore.yml` and fails if the measured error rates drift beyond the
  documented tolerances.
- `tests/test_illumina_coverage_quality.py` uses
  `IlluminaChannel.observe_error_rates` together with the presets defined in
  `src/genecoder/simulators/illumina/profiles.py` to guarantee the short-read
  channel matches its specification.

When new empirical data arrives you only need to update the profile files and
adjust the tolerances in the corresponding tests. Use the helper functions to
measure the new rates (optionally seeding `GENECODER_SIM_SEED` for repeatable
experiments) and tighten the assertions once the numbers stabilise. This keeps
future regression runs honest and provides a lightweight checklist for
contributors submitting improved sequencing statistics.


## Reproducible two-tier testing

The CI pipeline runs tests in two deterministic tiers:

1. **Core tier**: `pytest -m core --test-tier=core`
   - Targets the minimal dependency profile.
   - Must complete with **zero skipped tests**.
2. **Optional integration tier**: `pytest -m integration_optional --test-tier=integration`
   - Covers optional dependencies and external executables.
   - Skips are allowed when dependencies are unavailable.
   - A dependency availability report is generated via
     `python scripts/report_optional_test_dependencies.py`.

To reproduce CI behavior locally, run:

```bash
# Core (minimal)
python -m pip install -e . pytest pytest-xdist pytest-cov
pytest -m core --test-tier=core --junitxml=artifacts/core-junit.xml -q

# Optional integrations
poetry install --with gui,web,dev   --extras ldpc --extras fountain --extras bch   --extras raptorq --extras deepdna --extras chamaeleo   --no-interaction --no-root
python scripts/report_optional_test_dependencies.py
poetry run pytest -m integration_optional --test-tier=integration -rs -q
```

Keeping these commands and dependency profiles pinned in automation makes test
outcomes easier to compare across machines and over time.


## Required reproducibility artifact set (strict)

GeneCoder now defines the canonical reproducibility contract in
`configs/reproducibility.yaml`.

Required artifacts are validated by `scripts/validate_reproducibility_artifacts.py`.

- **Bundle run (`bundle_run`)**
  - `summary.json`
  - `sequence_batches.json`
  - `decoded/*.json`
  - `decoded/*.kpi.json`
- **Bundle sweep (`bundle_sweep`)**
  - `manifest_index.json`
  - `reproducibility_report.json`

Generate reports during execution:

```bash
genecli pipeline input.bin decoded.bin --codec reverse --channel none --seed 42 --emit-repro-report \
  --metrics-path artifacts/runs/repro-report/metrics.json
genecli bundle run configs/gold.yaml --cache-dir artifacts/runs/repro-bundle --emit-repro-report \
  --metrics-path artifacts/runs/repro-bundle/metrics.json
genecli bundle sweep configs/*.yaml --cache-dir artifacts/runs/repro-sweep --emit-repro-report \
  --metrics-path artifacts/runs/repro-sweep/metrics.json
```

Validate artifacts and tolerances in CI:

```bash
python scripts/validate_reproducibility_artifacts.py --artifact-root runs --mode bundle_sweep
```

## Reproducibility report interpretation

The generated report (`*.repro.json` for pipeline, `reproducibility_report.json`
for bundles) compares runs grouped by the same **simulation profile + global
seed** and enforces deterministic/tolerance checks from
`configs/reproducibility.yaml`.

- `summary.pass=true`: all deterministic expectations and tolerance gates passed.
- `summary.tolerance_violations>0`: one or more metrics drifted beyond configured
  limits.
- `summary.deterministic_violations>0`: one or more deterministic expectations
  (for example `decode_success == true`) were violated.
- `comparisons[].metric_checks[]`: per-metric baseline/candidate values and
  whether each check stayed within tolerance.

## Runtime reproducibility attestation

Every `RunPipelineUseCase` execution now emits a first-class attestation in the
canonical run schema and, when manifest output is enabled, in the generated
manifest. The top-level `run_fingerprint` is a SHA-256 digest of the canonical
attestation payload, not of wall-clock runtime fields. Re-running the same input
content, resolved configuration, profile parameters, seed provenance, package
versions and plugin lock state in the same environment produces the same
fingerprint even if artifact file names differ.

### Expected attestation schema

The run schema contains these top-level fields:

```json
{
  "run_fingerprint": "<64 lowercase hex sha256>",
  "attestation": {
    "schema_version": "genecoder.reproducibility.attestation.v1",
    "canonicalization": "json-sort-keys-separators-comma-colon-utf8",
    "hash_algorithm": "sha256",
    "payload": {
      "schema_version": "genecoder.reproducibility.attestation.v1",
      "config": {
        "codec": "reverse",
        "fec": null,
        "channel": "simple",
        "resolved_channel": "simple",
        "filter_mutated": false,
        "constraints": {},
        "sweep": {},
        "input": {
          "basename": "input.bin",
          "sha256": "<input content sha256>"
        }
      },
      "resolved_profiles": {
        "encoding": "reverse",
        "simulation": "simple",
        "decode": "reverse",
        "channel_profile": {
          "requested_name": "simple",
          "resolved_name": "simple",
          "parameters": {"substitution_prob": 0.0}
        }
      },
      "seed_provenance": {},
      "package_versions": {},
      "plugin_lock_state": []
    },
    "run_fingerprint": "<64 lowercase hex sha256>",
    "signature": {
      "algorithm": "RSASSA-PKCS1v15-SHA256",
      "padding_scheme": "pkcs1",
      "signature": "<base64 signature over canonical payload bytes>",
      "public_key_sha256": "<sha256 of signer public key pem>",
      "path": "artifacts/run.attestation.sig.json"
    }
  }
}
```

The same `run_fingerprint` and `attestation` object are copied into the manifest
JSON when `emit_manifest` is enabled.

### Verify a fingerprint

Use the canonicalization string recorded in the attestation: JSON with sorted
keys, compact comma/colon separators and UTF-8 bytes.

```bash
python - <<'PY'
import hashlib
import json
from pathlib import Path

run = json.loads(Path("artifacts/runs/example/metrics.json").read_text())
payload = run["attestation"]["payload"]
canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
fingerprint = hashlib.sha256(canonical).hexdigest()
assert fingerprint == run["run_fingerprint"] == run["attestation"]["run_fingerprint"]
print(fingerprint)
PY
```

If a manifest was emitted, verify that it carries the identical attestation:

```bash
python - <<'PY'
import json
from pathlib import Path

run = json.loads(Path("artifacts/runs/example/metrics.json").read_text())
manifest = json.loads(Path("artifacts/runs/example/metrics.manifest.json").read_text())
assert manifest["run_fingerprint"] == run["run_fingerprint"]
assert manifest["attestation"] == run["attestation"]
print("manifest attestation matches run schema")
PY
```

### Sign and verify an attestation payload

When `ArtifactOutputPolicy.attestation_private_key_path` is set, GeneCoder signs
the canonical attestation payload with the existing SHA-256 security primitives.
RSA private keys use PKCS#1 v1.5 signatures; ECDSA private keys use ECDSA with
SHA-256. If `ArtifactOutputPolicy.attestation_signature_path` is also set, a
copy of the detached signature metadata is written to that path.

Generate a local test key and run through the SDK/YAML path:

```bash
openssl genrsa -out artifacts/repro-attest-private.pem 2048
openssl rsa -in artifacts/repro-attest-private.pem -pubout -out artifacts/repro-attest-public.pem
cat > artifacts/repro-attest-request.yaml <<'YAML'
codec: reverse
input_path: examples/pipeline_demo_input.txt
output_path: artifacts/runs/repro-attest/decoded.txt
channel: none
seeds:
  global_seed: 42
artifacts:
  metrics_path: artifacts/runs/repro-attest/metrics.json
  emit_manifest: true
  attestation_private_key_path: artifacts/repro-attest-private.pem
  attestation_signature_path: artifacts/runs/repro-attest/attestation.sig.json
YAML
python - <<'PY'
from genecoder.sdk import run_experiment
run_experiment("artifacts/repro-attest-request.yaml")
PY
```

Verify the signature with `genecoder.plugin_security.verify_signature`, which is
the same verification helper used by plugin supply-chain checks:

```bash
python - <<'PY'
import base64
import json
from pathlib import Path
from genecoder.plugin_security import verify_signature

run = json.loads(Path("artifacts/runs/repro-attest/metrics.json").read_text())
attestation = run["attestation"]
canonical = json.dumps(attestation["payload"], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
signature = base64.b64decode(attestation["signature"]["signature"])
public_key = Path("artifacts/repro-attest-public.pem").read_bytes()
verified_digest = verify_signature(
    canonical,
    signature,
    public_key,
    padding_scheme=attestation["signature"].get("padding_scheme", "pkcs1"),
    expected_checksum=run["run_fingerprint"],
)
print(verified_digest)
PY
```
