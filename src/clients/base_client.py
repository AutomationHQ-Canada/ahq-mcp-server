import asyncio
import json
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
        # Every AHQ error response is the same ResponseObj envelope with a human-readable
        # "message" field — surfacing that directly (instead of the raw JSON blob) is the
        # difference between an LLM caller actually relaying "Another scheduler is already
        # scheduled within 1 hour of this time" to the user vs. it getting lost in noise
        # (confirmed live: this exact case, 2026-07-15). Falls back to the raw body if it isn't
        # JSON or has no "message" key.
        message = None
        try:
            parsed = json.loads(body)
            if isinstance(parsed, dict) and parsed.get("message"):
                message = parsed["message"]
        except (ValueError, TypeError):
            pass
        detail = message if message else body[:500]
        super().__init__(f"AHQ API error {status_code} ({reason}): {detail}")


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
                # A 200 whose body is the SPA's HTML means the request never reached the API —
                # classic symptom of AHQ_BASE_URL pointing at the web frontend (or a missing
                # token making the gateway serve the login shell). Surfacing it as an error here
                # turns "every tool returns garbage that looks like success" into one clear hint.
                if r.text.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
                    raise AhqApiError(
                        r.status_code, r.reason_phrase,
                        "Got the web frontend's HTML instead of an API response - check that "
                        "AHQ_BASE_URL is the API gateway (e.g. https://api-dev.automationhq.ai, "
                        "NOT the web UI) and that AHQ_API_TOKEN is set.",
                    )
                return {"status": r.status_code, "body": r.text}

    async def get(self, path: str, params: dict = None, extra_headers: dict = None, timeout: int = 30) -> dict:
        return await self._request("GET", f"{self._base}{path}", params=params, extra_headers=extra_headers, timeout=timeout)

    async def post(self, path: str, json: dict = None, params: dict = None, content: str = None, extra_headers: dict = None, timeout: int = 30) -> dict:
        return await self._request("POST", f"{self._base}{path}", json=json or {}, params=params, content=content, extra_headers=extra_headers, timeout=timeout)

    async def delete(self, path: str, params: dict = None, extra_headers: dict = None, timeout: int = 30) -> dict:
        return await self._request("DELETE", f"{self._base}{path}", params=params, extra_headers=extra_headers, timeout=timeout)

    async def put(self, path: str, json: dict = None, params: dict = None, extra_headers: dict = None, timeout: int = 30) -> dict:
        return await self._request("PUT", f"{self._base}{path}", json=json or {}, params=params, extra_headers=extra_headers, timeout=timeout)

    async def patch(self, path: str, json: dict = None, params: dict = None, extra_headers: dict = None, timeout: int = 30) -> dict:
        return await self._request("PATCH", f"{self._base}{path}", json=json, params=params, extra_headers=extra_headers, timeout=timeout)
