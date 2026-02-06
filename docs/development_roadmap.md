# Development Roadmap

1. **Foundation (Complete)** – command line interface, multiple encoders, error handling and a basic GUI with asynchronous operations.
2. **Phase 2: Robust Encoding Pipeline**
   - Introduce additional error correction codes such as Reed–Solomon and LDPC.
   - Implement streaming support for handling large files efficiently.
   - Refine GC-content balancing algorithms for more stable synthesis results.
3. **Phase 3: Simulation & Analysis**
   - Model sequencing errors in greater detail to mimic real-world conditions.
   - Provide named sequencing profiles (e.g., `miseq`, `hiseq`, `minion`,
     `promethion`) selectable via CLI options.
   - Integrate with common bioinformatics tools for downstream analysis.
   - Provide automated reports summarizing encoding accuracy and efficiency.
4. **Phase 4: Ecosystem & Automation**
   - Publish a plugin repository enabling community codecs and FEC modules.
   - Require digital signatures for plugins submitted to the new marketplace.
   - Offer workflow templates powered by n8n for routine processing tasks.
   - Package the toolkit for easy container deployment in research pipelines.
5. **Long-Term Vision**
   - Interactive dashboards to visualize storage simulations over time.
   - Cloud-friendly architecture for scaling large simulation batches.
   - Continued collaboration with the research community to expand features.

### Long-term interoperability strategy

To make ecosystem growth concrete, external tools should integrate through the
existing plugin entry points and registry workflows rather than bespoke
adapters. The implementation anchors are:

- [`docs/plugins.md`](plugins.md) for entry point groups, `register_*` hooks,
  and runtime loading rules.
- [`configs/registry.yaml`](../configs/registry.yaml) for registry schema fields
  (`name`, `version`, `spec`, `license`, `checksum`/`signature`) and trusted
  distribution patterns.
- [`plugins-examples/`](../plugins-examples/) for working package layouts,
  `pyproject.toml` entry point declarations, and minimal registration modules.

The roadmap supports three primary integration archetypes:

1. **External simulator wrapper plugin**
   - **Entry points:** `genecoder.simulators` and optional
     `genecoder.channels`.
   - **Input contract:** sequence payloads plus simulator/channel parameters
     provided from CLI/config profiles.
   - **Output contract:** deterministic simulation artifacts (mutated reads,
     per-read error metrics, and optional summary JSON compatible with pipeline
     reporting).
2. **Codec/FEC plugin**
   - **Entry points:** `genecoder.codecs` or `genecoder.fec`.
   - **Input contract:** binary/text payload bytes and plugin-specific coding
     parameters.
   - **Output contract:** encode/decode methods that round-trip payloads,
     expose parity/redundancy metadata, and return errors compatible with core
     validation paths.
3. **Visualizer plugin**
   - **Entry points:** `genecoder.visualizers`.
   - **Input contract:** standardized metrics/report structures produced by core
     pipeline commands.
   - **Output contract:** serializable figures or dashboard-ready artifacts that
     can be embedded in CLI/web reports without altering core data models.

#### External plugin compliance checklist

- Declare complete plugin metadata in packaging and registry records (name,
  version, entry point target, SPDX license identifier).
- Use an allowlisted license for registry distribution (see
  `docs/plugins.md` for accepted SPDX values).
- Include integrity material in registry entries: checksum is mandatory, and
  signature verification is required when registry policy enables signed
  artifacts.
- Follow safe package/URL constraints from the registry validation workflow
  before publication.
- Provide at least one runnable example under `plugins-examples/` (or equivalent
  structure) so maintainers can validate the entry point contract quickly.
6. **Documentation Updates**
   - Inline comments in `encoders.py` and `flet_app.py` now point to sections of the Development Vision PDF (Sections III and IV) for added context.

Refer to the [manifest format](manifest.md) for the current encoding metadata structure and the [plugin guide](plugins.md) for extension points that inform future roadmap items.
