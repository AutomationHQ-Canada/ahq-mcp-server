import json

import httpx

from src.clients.virtualization_client import VirtualizationClient


def _client_with_fake_transport(fake_request):
    client = VirtualizationClient()
    client._client.request = fake_request
    return client


async def test_base_url_uses_mtaf_sv_server_route():
    client = VirtualizationClient()
    assert client._base == "https://api-dev.automationhq.ai/mtaf-sv-server"


async def test_list_mock_mappings_sends_optional_filters():
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["url"] = url
        captured["params"] = kwargs["params"]
        return httpx.Response(200, json={"mappings": []}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    await client.list_mock_mappings(method="GET", search="users")

    assert captured["url"] == "https://api-dev.automationhq.ai/mtaf-sv-server/api/virtualization/get-mappings"
    assert captured["params"] == {"method": "GET", "search": "users"}


async def test_create_mock_mapping_sends_raw_json_as_text_plain():
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["content"] = kwargs["content"]
        captured["json"] = kwargs.get("json")
        captured["headers"] = kwargs["headers"]
        return httpx.Response(200, text='{"id": "m1", "uuid": "u1"}', request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    mapping = {"request": {"method": "GET", "url": "/api/example"}, "response": {"status": 200}}
    await client.create_mock_mapping(mapping)

    assert json.loads(captured["content"]) == mapping
    assert captured["json"] is None
    assert captured["headers"]["Content-Type"] == "text/plain"
