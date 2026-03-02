# API Reference

## Supported external integration surface

The only supported external integration surface is:

- `genecoder.sdk`
- `genecoder.app`

For plugin packages, use `genecoder.sdk.plugins`.

Deprecated modules are compatibility-only and versioned through `genecoder.compat.v1`:

- `genecoder.api` → `genecoder.sdk.plugins` (removal target: **v0.16.0**)
- `genecoder.pipeline` → `genecoder.app.pipeline_runtime` / `genecoder.app` contracts (removal target: **v0.16.0**)

## Package Root
::: genecoder

## SDK (Notebook-friendly)
::: genecoder.sdk

::: genecoder.sdk.api

::: genecoder.sdk.plugins

## App contracts
::: genecoder.app

## Encoders
::: genecoder.encoders

## FEC Modules
::: genecoder.fec

## Channels
::: genecoder.channels

## Simulators
::: genecoder.simulators

## Plugin System
::: genecoder.plugins

## CLI
::: genecoder.cli

## Web API
::: web.main
