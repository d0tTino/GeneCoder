# Contributing to GeneCoder

Thank you for your interest in improving GeneCoder! This project uses a few GitHub features and development tools that help keep the code base healthy. The most important pieces are summarized below.

## Merge Queue

All pull requests are merged through GitHub's **merge queue**. When you open a PR it enters the queue and GitHub creates a temporary merge commit that must pass the required `python-ci` check. Once that merge commit succeeds, your PR will automatically move to the front of the queue and merge. If the checks fail, the PR is removed from the queue until fixes are pushed.

## Automatic Merging for Comment‑Only Changes

The CI system can detect pull requests that only modify documentation, comments or docstrings. In that situation the `automerge-comments.yml` workflow enables auto-merge so the PR merges as soon as the basic checks finish. The detection logic lives in `scripts/only_comments_changed.py` and is also used to skip the heavy test matrix in the `python-ci` workflow.

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

