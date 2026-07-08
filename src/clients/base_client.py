import asyncio
import logging

import httpx

from src.config.ahq_services import settings
from src.config.credentials import AhqCredentials

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 502, 503, 504}
MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 0.5


class AhqApiError(Exception):
    def __init__(self, status_code: int, reason: str, body: str = ""):
        self.status_code = status_code
        self.body = body
        super().__init__(f"AHQ API error {status_code} ({reason}): {body[:500]}")


class BaseAhqClient:
    def __init__(
        self,
        service_prefix: str,
        credentials: AhqCredentials = None,
        http_client: httpx.AsyncClient = None,
    ):
        creds = credentials or AhqCredentials.from_settings(settings)
        self._credentials = creds
        self._base = f"{creds.base_url}{service_prefix}"
        self._headers = {
            "X-API-AUTH-KEY": creds.api_token,
            "org-id": creds.org_id,
            "projectId": creds.project_id,
            "Content-Type": "application/json",
        }
        self._client = http_client or httpx.AsyncClient()

    def _extra_headers(self, extra: dict) -> dict:
        return {**self._headers, **extra}

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict = None,
        json: dict = None,
        content: str = None,
        extra_headers: dict = None,
        timeout: int = 30,
    ) -> dict:
        headers = self._extra_headers(extra_headers) if extra_headers else self._headers

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                r = await self._client.request(
                    method, url, headers=headers, params=params,
                    json=json if content is None else None, content=content, timeout=timeout
                )
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.PoolTimeout) as exc:
                if attempt == MAX_ATTEMPTS:
                    raise
                logger.warning("AHQ request %s %s failed (%s), retrying (%d/%d)",
                                method, url, exc, attempt, MAX_ATTEMPTS)
                await asyncio.sleep(BACKOFF_BASE_SECONDS * 2 ** (attempt - 1))
                continue

            if r.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_ATTEMPTS:
                logger.warning("AHQ request %s %s got %d, retrying (%d/%d)",
                                method, url, r.status_code, attempt, MAX_ATTEMPTS)
                await asyncio.sleep(BACKOFF_BASE_SECONDS * 2 ** (attempt - 1))
                continue

            if r.status_code >= 400:
                raise AhqApiError(r.status_code, r.reason_phrase, r.text)

            if not r.content:
                return {}
            try:
                return r.json()
            except ValueError:
                return {"status": r.status_code, "body": r.text}

    async def get(self, path: str, params: dict = None, extra_headers: dict = None, timeout: int = 30) -> dict:
        return await self._request("GET", f"{self._base}{path}", params=params, extra_headers=extra_headers, timeout=timeout)

    async def post(self, path: str, json: dict = None, params: dict = None, extra_headers: dict = None, timeout: int = 30) -> dict:
        return await self._request("POST", f"{self._base}{path}", json=json or {}, params=params, extra_headers=extra_headers, timeout=timeout)

    async def delete(self, path: str, timeout: int = 30) -> dict:
        return await self._request("DELETE", f"{self._base}{path}", timeout=timeout)

    async def put(self, path: str, json: dict = None, params: dict = None, timeout: int = 30) -> dict:
        return await self._request("PUT", f"{self._base}{path}", json=json or {}, params=params, timeout=timeout)
