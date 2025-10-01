# GeneCoder: Simulated DNA Data Encoding & Exploration

[![Coverage Status](../coverage.svg)](https://codecov.io/gh/d0tTino/GeneCoder)

**An open, educational software toolkit for simulating DNA data encoding and decoding, bringing the concepts of molecular data storage to your fingertips.**

*The badge above reports the current coverage of GeneCoder's unit tests.* The coverage report intentionally **excludes** `src/genecoder/flet_app.py` via the `.coveragerc` configuration.

---

## Current Status: Evolving with New Features! 🚀

GeneCoder has been enhanced with new encoding strategies, error correction, batch processing and an improved GUI. The toolkit now offers sophisticated ways to simulate DNA data storage including GC-content balancing, triple-repeat error correction and batch processing.

For more details, explore the sections below.

* [Vertical Slice Guide](vertical_slice.md) – Quick setup and interface demo featuring the multi-oligo pipeline.
* [n8n Overview](n8n_overview.md) – Automate workflows with n8n.
* [Simulators](simulators.md) – Available read simulators and how to install external tools.
* [Performance Benchmarks](performance.md) – Encoding/decoding throughput numbers.
* [FEC Benchmarks](benchmarks.md) – Forward error correction examples and results.
* [Technology Stack](technology_stack.md) – Overview of dependencies and tooling.
* [Glossary](glossary.md) – Key terms used throughout the docs.
* [Usage Metrics](metrics.md) – Track encode and simulation counts.
* [Introductory Notebooks](../notebooks) – Encoding, channel simulation and decoding examples.
* [Lesson Notebooks](../notebooks/lessons) – Step-by-step guides for encoding basics, FEC, simulation and analysis.
* [MPI Pipeline Execution](mpi.md) – Run the channel pipeline across multiple nodes.

## Extending GeneCoder

* [Plugin System](plugins.md) – Step-by-step guide to writing codecs, FEC modules and simulators.
* [Plugin Packaging Tutorial](../notebooks/lessons/6_plugin_packaging.ipynb) – Interactive walkthrough of entry points.
* [Example Plugins](../plugins-examples) – Installable packages demonstrating each entry point group.
