# Contributing

Thank you for considering a contribution to GeneCoder. Contributions are
accepted under the terms of the project's MIT License.

## Licensing

By submitting changes, you agree that your contributions are licensed under
the MIT License and that any third-party code you introduce is compatible
with this license. Include appropriate attribution and ensure that licenses
for external dependencies are documented in `NOTICE`.

## Updating strategy model fields and generated docs

`docs/strategy_model.yaml` is the authoritative source for strategy phases, feature capabilities, KPI gates, and deployment posture fields.

When maintainers need to update strategy data:

1. Edit `docs/strategy_model.yaml` only (do not hand-edit generated strategy blocks).
2. Regenerate strategy sections:
   - `python scripts/render_strategy_docs.py --write`
3. Validate there is no drift:
   - `python scripts/check_strategy_docs_sync.py`
4. Include the regenerated changes in the same commit as the model update.

`last_validated_commit` is injected automatically from Git metadata during generation and should not be manually edited in generated blocks.

## Release validation stamp workflow

The strategy and roadmap snapshots in the following docs are release stamps that must point at the exact commit being promoted:

- `docs/product_strategy.md`
- `docs/development_roadmap.md`
- `docs/roadmap_execution.md`
- `docs/cloud.md`
- `docs/cloud_worker.md`

Use the workflow below when preparing a protected-branch release or release-candidate update:

1. Let the required QA jobs finish successfully in CI for the branch head you intend to release.
2. After those jobs are green, stamp the docs with the exact branch head:
   - `python scripts/stamp_validated_commits.py --write`
3. Review the doc-only diff to confirm every `last_validated_commit` value matches `git rev-parse HEAD`.
4. Commit the stamped docs and push them to the protected branch.
5. Confirm the protected-branch CI check passes; it will fail if any stamped document points at a different commit.

The protected-branch validation job intentionally runs this check only after the required QA jobs complete so the docs reflect a fully validated commit instead of an intermediate revision.
