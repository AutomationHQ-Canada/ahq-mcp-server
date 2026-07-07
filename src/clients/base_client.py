import httpx
from src.config.ahq_services import settings


class BaseAhqClient:
    def __init__(self, service_prefix: str):
        self._base = f"{settings.ahq_base_url}{service_prefix}"
        self._headers = {
            "X-API-AUTH-KEY": settings.ahq_api_token,
            "org-id": settings.ahq_org_id,
            "projectId": settings.ahq_project_id,
            "Content-Type": "application/json",
        }

    def _extra_headers(self, extra: dict) -> dict:
        return {**self._headers, **extra}

    async def get(self, path: str, params: dict = None, extra_headers: dict = None, timeout: int = 30) -> dict:
        headers = self._extra_headers(extra_headers) if extra_headers else self._headers
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self._base}{path}",
                headers=headers,
                params=params,
                timeout=timeout,
            )
            r.raise_for_status()
            return r.json()

    async def post(self, path: str, json: dict = None, extra_headers: dict = None, timeout: int = 30) -> dict:
        headers = self._extra_headers(extra_headers) if extra_headers else self._headers
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self._base}{path}",
                headers=headers,
                json=json or {},
                timeout=timeout,
            )
            r.raise_for_status()
            return r.json()

    async def delete(self, path: str, timeout: int = 30) -> dict:
        async with httpx.AsyncClient() as client:
            r = await client.delete(
                f"{self._base}{path}",
                headers=self._headers,
                timeout=timeout,
            )
            r.raise_for_status()
            return r.json()

    async def put(self, path: str, json: dict = None, timeout: int = 30) -> dict:
        async with httpx.AsyncClient() as client:
            r = await client.put(
                f"{self._base}{path}",
                headers=self._headers,
                json=json or {},
                timeout=timeout,
            )
            r.raise_for_status()
            return r.json()
