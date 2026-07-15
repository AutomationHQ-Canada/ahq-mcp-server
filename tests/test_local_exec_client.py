from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.clients.base_client import AhqApiError
from src.clients.local_exec_client import LocalExecClient


def _client_with_fake_transport(fake_request):
    client = LocalExecClient()
    client._client.request = fake_request
    return client


async def test_list_registered_agents_uses_real_path_and_orgId_header():
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["url"] = url
        captured["headers"] = kwargs["headers"]
        return httpx.Response(200, json=[{"id": "agent-1", "name": "Local Agent - Neon"}], request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.list_registered_agents()

    assert captured["url"] == "https://api-dev.automationhq.ai/ahq-standalone-local-v2-services/rest/api/local/agent/getAllAgents"
    assert captured["headers"]["orgId"] == "test-org"
    assert result == [{"id": "agent-1", "name": "Local Agent - Neon"}]


async def test_get_agent_status_online_past_warmup_returns_immediately():
    LocalExecClient.reset_warmup_tracking()
    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.json.return_value = {"message": "AutomationHQ Executor Service is running on your machine"}

    fake_async_client = AsyncMock()
    fake_async_client.__aenter__.return_value.get = AsyncMock(return_value=fake_response)

    # Already 100s into the warm-up window (e.g. a long-running agent) — no wait expected.
    clock = iter([100.0, 100.0])
    with patch("httpx.AsyncClient", return_value=fake_async_client):
        client = LocalExecClient(now=lambda: next(clock), sleep=AsyncMock())
        LocalExecClient._first_online_at = 0.0
        result = await client.get_agent_status()

    fake_async_client.__aenter__.return_value.get.assert_called_once()
    called_url = fake_async_client.__aenter__.return_value.get.call_args.args[0]
    assert called_url == "http://localhost:9202/rest/api/execute/ping"
    assert result == {"online": True, "data": {"message": "AutomationHQ Executor Service is running on your machine"}}
    client._sleep.assert_not_called()


async def test_get_agent_status_first_sighting_waits_out_warmup():
    LocalExecClient.reset_warmup_tracking()
    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.json.return_value = {"message": "running"}

    fake_async_client = AsyncMock()
    fake_async_client.__aenter__.return_value.get = AsyncMock(return_value=fake_response)
    fake_sleep = AsyncMock()

    with patch("httpx.AsyncClient", return_value=fake_async_client):
        client = LocalExecClient(now=lambda: 0.0, sleep=fake_sleep, warmup_seconds=15)
        result = await client.get_agent_status()

    fake_sleep.assert_called_once_with(15)
    assert result["online"] is True
    assert result["data"] == {"message": "running"}
    assert "just started" in result["note"]


async def test_get_agent_status_second_call_within_warmup_still_waits_remaining():
    LocalExecClient.reset_warmup_tracking()
    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.json.return_value = {"message": "running"}

    fake_async_client = AsyncMock()
    fake_async_client.__aenter__.return_value.get = AsyncMock(return_value=fake_response)
    fake_sleep = AsyncMock()

    clock = iter([0.0, 5.0])  # first sighting at t=0, second check at t=5, warmup=15 -> 10s left
    with patch("httpx.AsyncClient", return_value=fake_async_client):
        client = LocalExecClient(now=lambda: next(clock), sleep=fake_sleep, warmup_seconds=15)
        await client.get_agent_status()
        await client.get_agent_status()

    fake_sleep.assert_called_with(10)


async def test_get_agent_status_offline_when_unreachable():
    LocalExecClient.reset_warmup_tracking()
    fake_async_client = AsyncMock()
    fake_async_client.__aenter__.return_value.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

    with patch("httpx.AsyncClient", return_value=fake_async_client):
        client = LocalExecClient()
        result = await client.get_agent_status()

    assert result == {"online": False, "error": "Local agent not running at localhost:9202"}


async def test_execute_bot_locally_posts_directly_to_localhost_with_api_auth_key():
    # Shape confirmed by capturing a real browser HAR: the Run TestBot dialog, for a local-grid
    # execution, POSTs straight to localhost:9202 with org/project/partner identity headers.
    # X-API-AUTH-KEY IS required from us though (the browser instead sends its own user-session
    # JWT via Authorization, a mechanism our organization token can't use — confirmed live, twice,
    # that sending it as Authorization still 401s): TestBotExecutionController forwards it via
    # BearerTokenInterceptor to the agent's own downstream calls (fetch TestBot, vault, ...),
    # which 401 without it even though /execute itself succeeds.
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {"id": "job-1", "message": "Job is enqueued."}

    fake_async_client = AsyncMock()
    fake_async_client.__aenter__.return_value.post = AsyncMock(return_value=fake_response)

    with patch("httpx.AsyncClient", return_value=fake_async_client):
        client = LocalExecClient()
        result = await client.execute_bot_locally("bot-1", {"gridId": "g1"}, name="Run 1")

    call = fake_async_client.__aenter__.return_value.post.call_args
    assert call.args[0] == "http://localhost:9202/rest/api/bots/bot-1/execute"
    assert call.kwargs["json"] == {"testBotId": "bot-1", "executionConfiguration": {"gridId": "g1"}, "name": "Run 1"}
    headers = call.kwargs["headers"]
    assert headers["X-API-AUTH-KEY"] == client._credentials.api_token
    assert headers["org-id"] == "test-org"
    assert headers["organizationid"] == "test-org"
    assert headers["projectid"] == "test-project"
    assert "Authorization" not in headers
    assert result == {"id": "job-1", "message": "Job is enqueued."}


async def test_execute_bot_locally_surfaces_agent_error_body_on_failure():
    # Regression test: execute_bot_locally used to call bare raise_for_status(), which discards
    # the response body — a real agent-side 400 surfaced to the MCP caller as only "Client error
    # '400 '" with the actual reason lost (confirmed live 2026-07-15). It must raise the same
    # AhqApiError shape BaseAhqClient._request already uses for gateway-routed calls, carrying
    # the real body through.
    fake_response = MagicMock()
    fake_response.status_code = 400
    fake_response.reason_phrase = "Bad Request"
    fake_response.text = '{"message": "TestBot has no executable suites"}'

    fake_async_client = AsyncMock()
    fake_async_client.__aenter__.return_value.post = AsyncMock(return_value=fake_response)

    with patch("httpx.AsyncClient", return_value=fake_async_client):
        client = LocalExecClient()
        with pytest.raises(AhqApiError) as exc_info:
            await client.execute_bot_locally("bot-1", {"gridId": "g1"})

    assert "TestBot has no executable suites" in str(exc_info.value)


async def test_get_agent_status_offline_resets_warmup_tracking():
    LocalExecClient.reset_warmup_tracking()
    LocalExecClient._first_online_at = 999.0

    fake_async_client = AsyncMock()
    fake_async_client.__aenter__.return_value.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

    with patch("httpx.AsyncClient", return_value=fake_async_client):
        client = LocalExecClient()
        await client.get_agent_status()

    assert LocalExecClient._first_online_at is None
