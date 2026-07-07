import httpx

from src.clients.asset_client import AssetClient


def _client_with_fake_transport(fake_request):
    client = AssetClient()
    client._client.request = fake_request
    return client


async def test_list_websites_unwraps_paginated_content():
    async def fake_request(method, url, **kwargs):
        assert method == "GET"
        assert url == "https://api-dev.automationhq.ai/ahq-asset-services/rest/api/websites/list"
        assert kwargs["params"] == {"size": 1000}
        return httpx.Response(200, json={"content": [{"id": "1", "name": "Acme"}]}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.list_websites()

    assert result == [{"id": "1", "name": "Acme"}]


async def test_list_websites_returns_bare_list_as_is():
    async def fake_request(method, url, **kwargs):
        return httpx.Response(200, json=[{"id": "1"}], request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.list_websites()

    assert result == [{"id": "1"}]


async def test_create_website_posts_expected_body():
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["json"] = kwargs["json"]
        return httpx.Response(200, json={"id": "42", "name": "Acme"}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.create_website("Acme", "https://acme.example.com")

    assert result == {"id": "42", "name": "Acme"}
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api-dev.automationhq.ai/ahq-asset-services/rest/api/websites"
    assert captured["json"] == {"name": "Acme", "url": "https://acme.example.com"}


async def test_create_page_uses_pageName_pageUrl_fields():
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["json"] = kwargs["json"]
        return httpx.Response(200, json={"id": "7"}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    await client.create_page("site-1", "Login Page", "https://acme.example.com/login")

    assert captured["json"] == {"pageName": "Login Page", "pageUrl": "https://acme.example.com/login"}
