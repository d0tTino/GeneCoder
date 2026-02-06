# Vision & Core Concept

GeneCoder aims to make DNA data storage experimentation practical and reproducible by combining encoding, channel simulation, and decoding workflows in one toolkit.

## Vision and Current State

GeneCoder already ships an end-to-end simulation path for common DNA storage experiments. The current implementation includes:

- **Built-in sequencing simulators and presets** for **Illumina** and **Nanopore** workflows, including profile-driven runs in the bundled pipeline examples.
- A **storage decay stage** that can be chained after sequencing simulations in the preset bundles.
- End-to-end CLI presets in `configs/` (for example, the Gold, RS+Illumina, and Fountain+Nanopore pipelines) that exercise encode → simulate/decay → decode flows.

At the same time, the project still has fidelity work to do. The main gaps are not simulator availability, but:

- stronger calibration against wet-lab or public benchmark datasets,
- tighter reproducibility controls for cross-run benchmarking,
- and clearer parity validation versus external simulators under matched conditions.

### ECC and codec support status

GeneCoder currently documents and ships support for:

- **Reed–Solomon** and **Fountain** workflows in core presets/checklists,
- additional codec families through optional extras (for example Chamaeleo-backed schemes),
- and optional advanced integrations such as **LDPC**, **RaptorQ**, and AI-assisted **DNAformer/DeepDNA** components.

### Known limitations

Current limitations are primarily around validation depth and benchmarking rigor rather than missing baseline features:

- comparative validation datasets are still limited,
- benchmark reproducibility across environments can be improved,
- and advanced calibration workflows for profile tuning are still maturing.
