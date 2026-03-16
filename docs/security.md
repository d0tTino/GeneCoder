# Security Notes

GeneCoder encrypts data using AES-GCM with a random nonce. Previous releases also allowed XOR-based encryption for legacy reasons. The XOR branch is now deprecated.

Using data that is not prefixed with the `AESGCM1` header triggers a `DeprecationWarning` and will be removed in a future release. Ensure all encrypted files use AES-GCM.

## Secure plugin supply-chain workflow

### End-to-end install + verify

1. Create a registry entry with signed metadata and provenance:

```yaml
packages:
  - spec: https://plugins.example.org/acme_codec-1.4.2-py3-none-any.whl
    license: MIT
    checksum: "<sha256>"
    signature: "<base64-signature>"
    provenance_publisher: acme-bio
    provenance_channel: stable
```

2. Export trust roots and run installation:

```bash
export GENECODER_PLUGIN_REGISTRY_URL=file://$PWD/configs/registry.yaml
export GENECODER_PLUGIN_PUBLIC_KEY=$PWD/keys/plugin_pub.pem
genecli plugin install-registry --allow-registry --offline
```

3. If verification fails, the install aborts before package activation.

### Operational containment and rollback

When post-install policy checks fail in CI or staging, mark the plugin state:

```bash
genecli plugin disable acme_codec
# or
genecli plugin rollback acme_codec
```

- `disable` is for quarantine.
- `rollback` is for explicit reversion to a previous trusted release.
