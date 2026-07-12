"""
Slice 9e: Tunnel — 4 real endpoints on ahq-gateway-services (served at the gateway ROOT, no
service prefix). Every tunnel endpoint requires ROLE_TUNNEL_CLIENT, which the ORGANIZATION API
token does not carry — the client must mint a tunnel JWT via POST /token/tunnel first and send
it as Authorization: Bearer.
"""

import httpx

from src.clients.tunnel_client import TunnelClient


def _client_with_fake_transport(fake_request):
    client = TunnelClient()
    client._client.request = fake_request
    return client


async def test_tunnel_client_has_no_service_prefix():
    client = TunnelClient()
    assert client._base == client._credentials.base_url


async def test_status_mints_token_then_sends_bearer():
    calls = []

    async def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs.get("headers", {})))
        if url.endswith("/token/tunnel"):
            return httpx.Response(200, json={"tunnelToken": "jwt-abc"}, request=httpx.Request(method, url))
        return httpx.Response(200, json={"status": "RUNNING"}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.get_tunnel_status()

    assert result == {"status": "RUNNING"}
    assert calls[0][0] == "POST" and calls[0][1].endswith("/token/tunnel")
    assert calls[1][0] == "GET" and calls[1][1].endswith("/tunnel-launcher/status")
    assert calls[1][2]["Authorization"] == "Bearer jwt-abc"


async def test_execute_sends_raw_string_body_not_json():
    captured = {}

    async def fake_request(method, url, **kwargs):
        if url.endswith("/token/tunnel"):
            return httpx.Response(200, json={"tunnelToken": "jwt-abc"}, request=httpx.Request(method, url))
        captured["json"] = kwargs.get("json")
        captured["content"] = kwargs.get("content")
        return httpx.Response(200, json={}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    await client.execute_tunnel_command("run-suite smoke")

    # @RequestBody String on the controller — must go as raw content, never a JSON object
    assert captured["content"] == "run-suite smoke"
    assert captured["json"] is None


async def test_missing_tunnel_token_raises_clean_error():
    async def fake_request(method, url, **kwargs):
        return httpx.Response(200, json={"unexpected": "shape"}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    try:
        await client.start_tunnel()
        raise AssertionError("should have raised")
    except RuntimeError as e:
        assert "tunnelToken" in str(e)
