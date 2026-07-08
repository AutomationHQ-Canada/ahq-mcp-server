import httpx

from src.clients.test_mgmt_client import TestMgmtClient


def _client_with_fake_transport(fake_request):
    client = TestMgmtClient()
    client._client.request = fake_request
    return client


async def test_create_test_script_sends_testSteps_field():
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["json"] = kwargs["json"]
        return httpx.Response(200, json={"id": "s1"}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    steps = [{"templateId": "tmpl-1", "testStepTitle": "Click login"}]
    await client.create_test_script("Login Happy Path", steps, "page-1")

    assert captured["json"] == {"name": "Login Happy Path", "testSteps": steps, "pageId": "page-1"}


async def test_list_templates_uses_project_scoped_path():
    async def fake_request(method, url, **kwargs):
        assert method == "GET"
        assert url == "https://api-dev.automationhq.ai/ahq-test-management-services/rest/api/templates/test-project"
        assert kwargs["params"] == {"offset": 0}
        return httpx.Response(200, json={"content": [{"templateId": "tmpl-1", "templateTitle": "Click"}]}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.list_templates()

    assert result == [{"templateId": "tmpl-1", "templateTitle": "Click"}]


async def test_search_templates_sends_title_param():
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["url"] = url
        captured["params"] = kwargs["params"]
        return httpx.Response(200, json=[{"templateId": "tmpl-2", "templateTitle": "Navigate to URL"}], request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.search_templates("Navigate")

    assert captured["url"] == "https://api-dev.automationhq.ai/ahq-test-management-services/rest/api/templates/test-project/search"
    assert captured["params"] == {"title": "Navigate"}
    assert result == [{"templateId": "tmpl-2", "templateTitle": "Navigate to URL"}]


async def test_get_template_by_id():
    async def fake_request(method, url, **kwargs):
        assert url == "https://api-dev.automationhq.ai/ahq-test-management-services/rest/api/templates/tmpl-1"
        return httpx.Response(200, json={"templateId": "tmpl-1", "templateTitle": "Click", "params": [{"name": "uiLocator", "type": "STRING"}]}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.get_template("tmpl-1")

    assert result["templateId"] == "tmpl-1"
    assert result["params"][0]["name"] == "uiLocator"
