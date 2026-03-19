# Cloud Status

> last_validated_commit: `4eb89f0cde3b7d75fcaf8311634be19ec56b90f0`

## Runtime-reported deployment posture

The current shipped runtime capability manifest reports:

- `execution_mode`: `local-only`
- `queue_backend`: `none`
- `remote_worker`: `false`
- `supports_async_jobs`: `false`

You can verify these values directly from `GET /capabilities` or `GET /health`.

## Non-goals and current constraints

- No managed cloud control plane is provided in the current release.
- No remote queue workers are supported because the runtime manifest reports `remote_worker=false`.
- No queue-backed async job submission is supported because the runtime manifest reports `queue_backend=none`.
- No SLA for distributed retries, preemption, or cross-node artifact durability.
- Service contract endpoints such as dry-run planning validate requests only and currently return local inline execution metadata.
