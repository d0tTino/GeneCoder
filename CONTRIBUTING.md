# Contributing to GeneCoder

Thank you for your interest in improving GeneCoder! This project uses a few GitHub features and development tools that help keep the code base healthy. The most important pieces are summarized below.

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
pip install pre-commit
pre-commit install
```

You can then run the checks against all files with:

```bash
pre-commit run --all-files
```

Or restrict it to specific files:

```bash
pre-commit run --files path/to/file.py
```

The hook also runs automatically on each commit if installed.

## Running the Test Suite

Unit tests use `pytest`. Install the pinned dependencies and run:

```bash
pip install -r requirements.lock
pytest -q
```

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
   python -m pip install build twine
   python -m build
   twine upload dist/*
   ```

5. Create a GitHub release pointing at the same tag.

