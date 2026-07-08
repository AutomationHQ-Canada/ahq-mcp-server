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


async def test_list_pages_unwraps_object_repository_shape():
    # The real endpoint returns an ObjectRepository ({"name": ..., "pages": [...]}),
    # not {"content": [...]} like other list endpoints in this service.
    async def fake_request(method, url, **kwargs):
        return httpx.Response(200, json={"name": "Object Repository", "pages": [{"pageId": "p1", "pageName": "Login"}]}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.list_pages("site-1")

    assert result == [{"pageId": "p1", "pageName": "Login"}]


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


async def test_add_locators_sends_raw_page_array_not_wrapped_object():
    # pushSpyElements takes @RequestBody List<Page> - a bare JSON array of full page objects
    # with locators embedded, not {"pageId": ..., "elements": [...]}.
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs["json"]
        captured["headers"] = kwargs["headers"]
        return httpx.Response(200, json={"message": "ok"}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    locators = [{"locatorName": "Email input", "locatorType": "input", "locationStrategies": [{"locateBy": "css", "locatorValue": "input#email", "selected": True}]}]
    await client.add_locators("page-1", "site-1", "https://acme.example.com/login", "Login Page", locators)

    assert captured["url"] == "https://api-dev.automationhq.ai/ahq-asset-services/rest/api/locators/pushSpyElements"
    assert captured["json"] == [{
        "pageId": "page-1",
        "pageName": "Login Page",
        "pageUrl": "https://acme.example.com/login",
        "websiteId": "site-1",
        "locators": locators,
    }]
    assert captured["headers"]["websiteId"] == "site-1"


async def test_add_locators_backfills_deprecated_locateBy_locatorValue_from_strategy():
    # ActionLibraryServices.getLocatorBy()/getLocatorValue() (ahq-actions-commons) crashes with an
    # NPE at execution time if the deprecated singular locateBy is null, even though
    # locationStrategies is populated (confirmed live) - a real backend bug, worked around here by
    # mirroring what the UI's own locator-creation flow does: always double-write both.
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["json"] = kwargs["json"]
        return httpx.Response(200, json={"message": "ok"}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    locators = [{
        "locatorName": "Email input",
        "locatorType": "input",
        "locationStrategies": [
            {"locateBy": "xpath", "locatorValue": "//input[@id='old']", "selected": False},
            {"locateBy": "css", "locatorValue": "input#email", "selected": True},
        ],
    }]
    await client.add_locators("page-1", "site-1", "https://acme.example.com/login", "Login Page", locators)

    sent_locator = captured["json"][0]["locators"][0]
    assert sent_locator["locateBy"] == "css"
    assert sent_locator["locatorValue"] == "input#email"


async def test_update_locator_sends_correct_path_and_body():
    # The only way to fix an already-created locator — add_locators/pushSpyElements silently
    # no-ops for anything matching an existing locationStrategies value, it never updates.
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["json"] = kwargs["json"]
        return httpx.Response(200, json={"message": "Locator updated successfully"}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.update_locator(
        website_id="site-1", page_id="page-1", locator_id="loc-1",
        locator_name="Email input", locator_type="input",
        locate_by="css", locator_value="input#email",
    )

    assert captured["method"] == "PUT"
    assert captured["url"] == "https://api-dev.automationhq.ai/ahq-asset-services/rest/api/websites/site-1/pages/page-1/locator/loc-1"
    assert captured["json"] == {
        "locatorId": "loc-1",
        "locatorName": "Email input",
        "locatorType": "input",
        "locateBy": "css",
        "locatorValue": "input#email",
        "locationStrategies": [{"locateBy": "css", "locatorValue": "input#email", "selected": True}],
    }
    assert result == {"message": "Locator updated successfully"}


async def test_add_locators_does_not_override_explicit_locateBy():
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["json"] = kwargs["json"]
        return httpx.Response(200, json={"message": "ok"}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    locators = [{
        "locatorName": "Email input",
        "locatorType": "input",
        "locateBy": "id",
        "locatorValue": "email-field",
        "locationStrategies": [{"locateBy": "css", "locatorValue": "input#email", "selected": True}],
    }]
    await client.add_locators("page-1", "site-1", "https://acme.example.com/login", "Login Page", locators)

    sent_locator = captured["json"][0]["locators"][0]
    assert sent_locator["locateBy"] == "id"
    assert sent_locator["locatorValue"] == "email-field"
