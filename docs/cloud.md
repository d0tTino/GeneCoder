# Cloud Status

> last_validated_commit: `4eb89f0cde3b7d75fcaf8311634be19ec56b90f0`

## Deployment posture

- `cloud_enabled`: `False`
- `cloud_worker_enabled`: `False`
- `local_execution_only`: `True`

## Non-goals and current constraints

- No managed cloud control plane is provided in the current release.
- No remote queue workers are supported; all jobs execute in-process on the local host.
- No SLA for distributed retries, preemption, or cross-node artifact durability.
- New service contract endpoints (for example dry-run planning) validate requests only and do not imply remote execution guarantees.
