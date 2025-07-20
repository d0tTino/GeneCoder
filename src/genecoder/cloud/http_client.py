from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - used for type hints only
    import httpx


class HTTPClient:
    """Thin wrapper around ``httpx.Client``."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        import httpx

        self._client = httpx.Client(*args, **kwargs)

    def post(self, *args: object, **kwargs: object) -> "httpx.Response":
        return self._client.post(*args, **kwargs)

    def get(self, *args: object, **kwargs: object) -> "httpx.Response":
        return self._client.get(*args, **kwargs)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HTTPClient":
        self._client.__enter__()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:  # pragma: no cover - passthrough
        self._client.__exit__(exc_type, exc, tb)

    def __getattr__(self, name: str) -> object:
        return getattr(self._client, name)


class AsyncHTTPClient:
    """Thin wrapper around ``httpx.AsyncClient``."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        import httpx

        self._client = httpx.AsyncClient(*args, **kwargs)

    async def post(self, *args: object, **kwargs: object) -> "httpx.Response":
        return await self._client.post(*args, **kwargs)

    async def get(self, *args: object, **kwargs: object) -> "httpx.Response":
        return await self._client.get(*args, **kwargs)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "AsyncHTTPClient":
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:  # pragma: no cover - passthrough
        await self._client.__aexit__(exc_type, exc, tb)

    def __getattr__(self, name: str) -> object:
        return getattr(self._client, name)


__all__ = ["HTTPClient", "AsyncHTTPClient"]
