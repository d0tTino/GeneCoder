# Cloud Worker Status

> last_validated_commit: `4eb89f0cde3b7d75fcaf8311634be19ec56b90f0`

## Runtime-reported deployment posture

The current shipped runtime capability manifest reports:

- `execution_mode`: `local-only`
- `queue_backend`: `none`
- `remote_worker`: `false`

That means GeneCoder does **not** advertise a remote worker control plane in the current release. Check `GET /capabilities` for the live values exposed by a running deployment.
