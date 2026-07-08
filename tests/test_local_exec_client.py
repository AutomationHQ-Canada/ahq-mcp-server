from unittest.mock import AsyncMock, MagicMock, patch

import httpx

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


async def test_get_agent_status_online_hits_execute_ping():
    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.json.return_value = {"message": "AutomationHQ Executor Service is running on your machine"}

    fake_async_client = AsyncMock()
    fake_async_client.__aenter__.return_value.get = AsyncMock(return_value=fake_response)

    with patch("httpx.AsyncClient", return_value=fake_async_client):
        client = LocalExecClient()
        result = await client.get_agent_status()

    fake_async_client.__aenter__.return_value.get.assert_called_once()
    called_url = fake_async_client.__aenter__.return_value.get.call_args.args[0]
    assert called_url == "http://localhost:9202/rest/api/execute/ping"
    assert result == {"online": True, "data": {"message": "AutomationHQ Executor Service is running on your machine"}}


async def test_get_agent_status_offline_when_unreachable():
    fake_async_client = AsyncMock()
    fake_async_client.__aenter__.return_value.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

    with patch("httpx.AsyncClient", return_value=fake_async_client):
        client = LocalExecClient()
        result = await client.get_agent_status()

    assert result == {"online": False, "error": "Local agent not running at localhost:9202"}
