from __future__ import annotations

from typing import Any
from types import TracebackType

import httpx


class HTTPClient:
    """Thin wrapper around ``httpx.Client``."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        self._client = httpx.Client(*args, **kwargs)

    def post(self, *args: Any, **kwargs: Any) -> httpx.Response:  # noqa: ANN401
        return self._client.post(*args, **kwargs)

    def get(self, *args: Any, **kwargs: Any) -> httpx.Response:  # noqa: ANN401
        return self._client.get(*args, **kwargs)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HTTPClient":
        self._client.__enter__()
        return self

    def __exit__(self, exc_type: type | None, exc: BaseException | None, tb: TracebackType | None) -> None:  # pragma: no cover - passthrough
        self._client.__exit__(exc_type, exc, tb)

    def __getattr__(self, name: str) -> object:
        return getattr(self._client, name)


class AsyncHTTPClient:
    """Thin wrapper around ``httpx.AsyncClient``."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        self._client = httpx.AsyncClient(*args, **kwargs)

    async def post(self, *args: Any, **kwargs: Any) -> httpx.Response:  # noqa: ANN401
        return await self._client.post(*args, **kwargs)

    async def get(self, *args: Any, **kwargs: Any) -> httpx.Response:  # noqa: ANN401
        return await self._client.get(*args, **kwargs)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "AsyncHTTPClient":
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type: type | None, exc: BaseException | None, tb: TracebackType | None) -> None:  # pragma: no cover - passthrough
        await self._client.__aexit__(exc_type, exc, tb)

    def __getattr__(self, name: str) -> object:
        return getattr(self._client, name)


__all__ = ["HTTPClient", "AsyncHTTPClient"]
