from __future__ import annotations

from typing import Any


class CloudClient:
    """Minimal REST client for submitting jobs to a remote worker."""

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        client: Any | None = None,
    ) -> None:
        import httpx

        self.base_url = base_url.rstrip("/")
        self.token = token
        self._client = client or httpx.Client(base_url=self.base_url)

    def submit(self, job_type: str, payload: dict[str, Any]) -> str:
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        import httpx

        try:
            resp = self._client.post(
                "/jobs", json={"type": job_type, "payload": payload}, headers=headers
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - network errors
            raise RuntimeError(f"Failed to submit job: {exc}") from exc

        data = resp.json()
        job_id = data.get("job_id")
        if not isinstance(job_id, str):
            raise ValueError("Invalid response from server")
        return job_id

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CloudClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        self.close()

class AsyncCloudClient:
    """Asynchronous REST client for submitting jobs to a remote worker."""

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        client: Any | None = None,
    ) -> None:
        import httpx

        self.base_url = base_url.rstrip("/")
        self.token = token
        self._client = client or httpx.AsyncClient(base_url=self.base_url)

    async def submit(self, job_type: str, payload: dict[str, Any]) -> str:
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        import httpx

        try:
            resp = await self._client.post(
                "/jobs", json={"type": job_type, "payload": payload}, headers=headers
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - network errors
            raise RuntimeError(f"Failed to submit job: {exc}") from exc

        data = resp.json()
        job_id = data.get("job_id")
        if not isinstance(job_id, str):
            raise ValueError("Invalid response from server")
        return job_id

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "AsyncCloudClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        await self.close()


__all__ = ["CloudClient", "AsyncCloudClient"]
