# Manifest Format

Each encoded file generates a JSON manifest describing the encoding process.
The manifest has three top-level keys:

```json
{
  "file": "<input file name>",
  "encoding_parameters": {
    "method": "<encoding method>"
  },
  "metrics": {}
}
```

`encoding_parameters` must at least contain a `method` field identifying the
encoder used. Additional keys mirror the options supplied on the CLI or GUI.
If required keys are missing an error will be raised when creating the manifest.

See the [development roadmap](development_roadmap.md) for planned enhancements
to the manifest format and for the canonical phase framework (numbering, names,
and KPI gates), and the [plugin guide](plugins.md) for ways plugins can extend
encoding parameters reflected in the manifest.
