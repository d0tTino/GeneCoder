# Command Architecture Layers

GeneCoder now follows a transport-agnostic application service architecture.

## Layers

- **Transport adapters**
  - CLI modules in `src/genecoder/cli/`
  - HTTP API handlers in `web/main.py`
  - SDK wrappers in `src/genecoder/sdk/api.py`
- **Application services** (`src/genecoder/app/`)
  - `EncodeUseCase`
  - `RunPipelineUseCase`
  - `AnalyzeUseCase`
- **Domain & orchestration**
  - Encoding/decoding primitives, constraints, and channel simulation in `src/genecoder/`
- **Plugin boundary**
  - Codecs/FEC/channels resolved via plugin registries in `genecoder.plugin_manager`

## Data contracts

Each use-case exposes explicit request/response dataclasses to avoid untyped dict coupling:

- `EncodeRequest` / `EncodeResponse`
- `RunPipelineRequest` / `RunPipelineResponse`
- `AnalyzeRequest` / `AnalyzeResponse`

Adapters are responsible for argument parsing and serialization only. Business orchestration, validation, and output shaping run in the application service layer.

## Compatibility strategy

Large CLI modules are decomposed incrementally by command group. Existing subcommand UX is preserved by compatibility wrappers in CLI handlers that delegate to use-cases.
