# Package Architecture Boundaries

GeneCoder uses explicit package boundaries to keep integrations clean and to
avoid long-term wrapper accumulation.

## Layer map

| Layer | Packages | Responsibility |
| --- | --- | --- |
| Domain | `genecoder.coding`, `genecoder.constraints`, `genecoder.simulators` | Core DNA coding, constraints, and channel/simulator behavior. |
| Application | `genecoder.app` | Use-cases and orchestration contracts (`RunPipelineUseCase`, `EncodeUseCase`, `AnalyzeUseCase`). |
| Interfaces | `genecoder.cli`, `genecoder.dashboard`, `genecoder.dashboard_streamlit`, `genecoder.sdk` | User/program entry points that parse IO and call application services. |
| Infrastructure | `genecoder.plugin_runtime`, `genecoder.*_adapter` modules | Plugin runtime, registry integration, and external-tool adapters. |
| Compatibility | `genecoder.pipeline`, `genecoder.api`, `genecoder.channel_sim` | Legacy import shims only; no new behavior is allowed here. |

## Dependency direction

Allowed direction is intentionally one-way:

- Interfaces -> Application -> Domain
- Infrastructure can depend on Domain/Application internals where needed, but
  must not depend on Interface packages.
- Domain must not depend on Application or Interface packages.
- Compatibility modules may forward to modern packages but must not gain new
  business logic.

## Enforced checks

Boundary checks run in `tests/test_architecture_boundaries.py` and are wired into
CI. They verify:

1. Interface packages do not import marked legacy modules.
2. Marked legacy modules are imported only by approved compatibility adapters.
3. Domain/Application/Infrastructure packages respect layer dependency rules.

## Why this matters

These checks make architectural drift visible at review time and ensure that new
integrations are implemented in the target layers instead of adding additional
legacy wrappers.
