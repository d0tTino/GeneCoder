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
