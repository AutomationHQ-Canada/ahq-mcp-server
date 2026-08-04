import httpx
import pytest

from src.clients.base_client import AhqApiError, BaseAhqClient, MAX_ATTEMPTS


def _client_with_fake_transport(fake_request):
    client = BaseAhqClient("/svc")
    client._client.request = fake_request
    return client


async def test_get_succeeds_on_first_try():
    calls = []

    async def fake_request(method, url, **kwargs):
        calls.append((method, url))
        return httpx.Response(200, json={"ok": True}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.get("/ping")

    assert result == {"ok": True}
    assert len(calls) == 1
    assert calls[0] == ("GET", "https://api-dev.automationhq.ai/svc/ping")


async def test_retries_on_503_then_succeeds():
    calls = {"n": 0}

    async def fake_request(method, url, **kwargs):
        calls["n"] += 1
        if calls["n"] < MAX_ATTEMPTS:
            return httpx.Response(503, request=httpx.Request(method, url))
        return httpx.Response(200, json={"ok": True}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.get("/ping")

    assert result == {"ok": True}
    assert calls["n"] == MAX_ATTEMPTS


async def test_exhausts_retries_and_raises_on_persistent_503():
    calls = {"n": 0}

    async def fake_request(method, url, **kwargs):
        calls["n"] += 1
        return httpx.Response(503, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)

    with pytest.raises(AhqApiError) as exc_info:
        await client.get("/ping")

    assert exc_info.value.status_code == 503
    assert calls["n"] == MAX_ATTEMPTS


async def test_404_raises_immediately_without_retry():
    calls = {"n": 0}

    async def fake_request(method, url, **kwargs):
        calls["n"] += 1
        return httpx.Response(404, text="not found", request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)

    with pytest.raises(AhqApiError) as exc_info:
        await client.get("/missing")

    assert exc_info.value.status_code == 404
    assert calls["n"] == 1


async def test_error_extracts_human_readable_message_from_response_obj_envelope():
    # Every AHQ error response is the same ResponseObj envelope with a human-readable "message"
    # field — surfacing that directly (instead of the raw JSON blob) is what makes an LLM caller
    # actually relay the real reason instead of it getting lost in noise (confirmed live: a 400
    # whose real cause, "Another scheduler is already scheduled within 1 hour of this time," was
    # buried in a ~300-char JSON envelope before this fix).
    async def fake_request(method, url, **kwargs):
        body = '{"timestamp":"2026-07-15T13:29:03.954Z","message":"Another scheduler is already scheduled within 1 hour of this time. Please choose a different time slot.","status":400,"success":false}'
        return httpx.Response(400, text=body, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)

    with pytest.raises(AhqApiError) as exc_info:
        await client.get("/things")

    assert str(exc_info.value) == (
        "TestBots API error 400 (Bad Request): Another scheduler is already scheduled "
        "within 1 hour of this time. Please choose a different time slot."
    )
    assert "timestamp" not in str(exc_info.value)  # the raw envelope must not leak through


async def test_error_falls_back_to_raw_body_when_not_json():
    async def fake_request(method, url, **kwargs):
        return httpx.Response(400, text="plain text error, not JSON", request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)

    with pytest.raises(AhqApiError) as exc_info:
        await client.get("/things")

    assert "plain text error, not JSON" in str(exc_info.value)


async def test_error_falls_back_to_raw_body_when_json_has_no_message():
    async def fake_request(method, url, **kwargs):
        return httpx.Response(400, text='{"status":400,"success":false}', request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)

    with pytest.raises(AhqApiError) as exc_info:
        await client.get("/things")

    assert '{"status":400,"success":false}' in str(exc_info.value)


async def test_connect_error_retries_then_succeeds():
    calls = {"n": 0}

    async def fake_request(method, url, **kwargs):
        calls["n"] += 1
        if calls["n"] < MAX_ATTEMPTS:
            raise httpx.ConnectError("connection refused", request=httpx.Request(method, url))
        return httpx.Response(200, json={"ok": True}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.get("/ping")

    assert result == {"ok": True}
    assert calls["n"] == MAX_ATTEMPTS


async def test_connect_error_exhausts_retries_and_reraises():
    async def fake_request(method, url, **kwargs):
        raise httpx.ConnectError("connection refused", request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)

    with pytest.raises(httpx.ConnectError):
        await client.get("/ping")


async def test_post_sends_json_body():
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured.update(kwargs)
        return httpx.Response(200, json={"id": "1"}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.post("/things", json={"name": "widget"})

    assert result == {"id": "1"}
    assert captured["json"] == {"name": "widget"}


async def test_empty_response_body_returns_empty_dict():
    async def fake_request(method, url, **kwargs):
        return httpx.Response(204, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.delete("/things/1")

    assert result == {}
