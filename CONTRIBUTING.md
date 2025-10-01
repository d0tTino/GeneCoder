# Contributing to GeneCoder

Thank you for your interest in improving GeneCoder! Contributions are accepted under the terms of the MIT License. By submitting a pull request you agree to license your work under the MIT License. This project uses a few GitHub features and development tools that help keep the code base healthy. The most important pieces are summarized below.

## Merge Queue

All pull requests are merged through GitHub's **merge queue**. When you open a PR it enters the queue and GitHub creates a temporary merge commit that must pass the required `python-ci` check. Once that merge commit succeeds, your PR will automatically move to the front of the queue and merge. If the checks fail, the PR is removed from the queue until fixes are pushed.

## Automatic Merging for Comment‑Only Changes

The CI system can detect pull requests that only modify documentation, comments or docstrings. In that situation the `automerge-comments.yml` workflow enables auto-merge so the PR merges as soon as the basic checks finish. The detection logic lives in `scripts/only_comments_changed.py` and is also used to skip the heavy test matrix in the `python-ci` workflow.

### Checking your branch locally

You can run the detection script yourself to see if your changes qualify as
comment-only. Execute it from the repository root:

```bash
python scripts/only_comments_changed.py
```

By default it compares the working tree against `origin/main`. Set `BASE_SHA`
to override the reference if your branch uses a different base. When the script
prints `only_comments=true` the CI workflow will auto-merge once the lightweight
checks pass.

## Running `pre-commit` Locally

Code style is enforced with [pre-commit](https://pre-commit.com/). Install the tool and set up the git hook:

```bash
poetry run pip install pre-commit
poetry run pre-commit install
```

You can then run the checks against all files with:

```bash
pre-commit run --all-files
```

Or restrict it to specific files:

```bash
pre-commit run --files path/to/file.py
```

When developing plugins in `plugins-examples/`, include the package path so Ruff
and mypy lint those files as well:

```bash
pre-commit run --files plugins-examples/example_codec/example_codec/__init__.py
```

### Migrating plugins to `SequenceBatch`

Simulators must now accept and return ``genecoder.formats.SequenceBatch``
instances. To update an existing string-based plugin:

1. Convert any incoming ``str`` to a batch with
   ``SequenceBatch.build(..., batch_seed=secrets.randbits(32))`` so oligo IDs and
   seeds are populated automatically.
2. Use ``genecoder.simulators.batch_utils.clone_batch`` to work on a copy of the
   source batch and preserve metadata.
3. Populate coverage, dropout and synthesis results via
   ``genecoder.simulators.batch_utils.RESULT_*`` constants and finish with
   ``finalize_batch_statistics`` to keep aggregate metadata in sync.
4. Opt into the compatibility layer by calling
   ``apply_legacy_simulator`` when you need to adapt an older ``str``-only
   simulator. The helper takes care of all metadata bookkeeping.

``mypy`` validates the plugin templates in ``plugins-examples/`` to ensure these
hooks stay exercised. Run ``mypy --config-file mypy.ini`` locally after editing
examples to confirm your plugin still satisfies the updated protocol.

The hook also runs automatically on each commit if installed.

CI runs `ruff check` and `mypy` on pull requests that modify code. Fix any
issues they report before merging.

### Running `mypy` Manually

Install the development extras so stub packages like `types-PyYAML` are
available. `mypy` relies on this stub package for YAML type checking, so
ensure it is installed before running:

```bash
python -m pip install -e .[dev]
mypy --config-file pyproject.toml --show-error-codes
```

An additional `check-glossary-terms` hook verifies that every term in
`docs/glossary.json` appears in at least one Markdown file. The commit
will fail if any terms are missing.
The `markdown-link-check` hook scans `README.md` and all Markdown files
in `docs/` to verify that hyperlinks are still valid.
The `python-ci` workflow also runs this script in a dedicated job after linting
to catch missing terms in pull requests.

## Running the Test Suite

Unit tests use `pytest`. Install the pinned dependencies and run:

```bash
poetry install --with gui,web,dev --no-interaction
poetry run pytest -q
```

### Optional Test Dependencies

Some integration tests use optional GUI and web components. Install these extras
with:

```bash
poetry install --with gui,web --no-interaction
```

To run **all** tests, including those covering optional codecs and machine
learning models, install every extras group:

```bash
poetry install --with gui,web,dnaformer,deepdna,ldpc,fountain,raptorq,bch,framed --no-interaction
```

You can also run `scripts/setup_test_env.sh` to install the same extras.

All code changes must pass `pre-commit` and the test suite. These checks are not
required for documentation-only pull requests.

## Making a Release

Follow these steps to publish a new version:

1. Update `CHANGELOG.md` with a new version heading and notes.
2. Bump the version in `pyproject.toml` and `CITATION.cff`.
3. Commit the changes and create an annotated tag:

   ```bash
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push --tags
   ```

4. Build and upload the package to PyPI:

   ```bash
   poetry run pip install build twine
   poetry run python -m build
   poetry run twine upload dist/*
   ```

5. Create a GitHub release pointing at the same tag.

## Publishing Plugins to the Marketplace

Plugins intended for distribution must be signed using the helper scripts in
`plugins-examples/signing/`. Once signed, submit the package through the new
marketplace process described in `docs/plugins.md`. Marketplace reviewers verify
the signature before the plugin is listed.

