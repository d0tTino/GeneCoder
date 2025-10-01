# Channel Plugin Template

Minimal skeleton for a custom channel plugin. Implement the
``SequenceBatch``-aware ``simulate`` method in
`channel_template/__init__.py` and adjust the entry point name in
`pyproject.toml`. The template shows how to emit batch IDs, simulator
seeds and per-oligo coverage values.

Install locally for experimentation:

```bash
pip install ./channel_template
```
