import httpx

from src.clients.managed_testing_client import ManagedTestingClient


def _client_with_fake_transport(fake_request):
    client = ManagedTestingClient()
    client._client.request = fake_request
    return client


async def test_base_url_uses_mtaf_core_route_not_repo_name():
    client = ManagedTestingClient()
    assert client._base == "https://api-dev.automationhq.ai/mtaf-core"


async def test_list_api_collections_unwraps_data_field():
    async def fake_request(method, url, **kwargs):
        assert url == "https://api-dev.automationhq.ai/mtaf-core/rest/api/v2/collections/list"
        return httpx.Response(200, json={"message": "ok", "status": 200, "data": [{"id": "c1", "name": "Users API"}]}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.list_api_collections()

    assert result == [{"id": "c1", "name": "Users API"}]


async def test_test_api_request_sends_request_variables_dataRow_envelope():
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["json"] = kwargs["json"]
        return httpx.Response(200, json={"status": 200}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    req = {"name": "Get user", "method": "GET", "url": "https://api.example.com/users/1"}
    await client.test_api_request(req, variables={"token": "abc"})

    assert captured["method"] == "POST"
    assert captured["url"] == "https://api-dev.automationhq.ai/mtaf-core/rest/api/v2/requests/test"
    assert captured["json"] == {"request": req, "variables": {"token": "abc"}, "dataRow": {}}


async def test_import_curl_sends_raw_text_body_not_json():
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["params"] = kwargs["params"]
        captured["content"] = kwargs["content"]
        captured["json"] = kwargs.get("json")
        captured["headers"] = kwargs["headers"]
        return httpx.Response(200, json={"status": 200, "importedCount": 1}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.import_curl("curl https://api.example.com/users", collection_id="c1")

    assert captured["url"] == "https://api-dev.automationhq.ai/mtaf-core/rest/api/v2/import/curl"
    assert captured["content"] == "curl https://api.example.com/users"
    assert captured["json"] is None
    assert captured["params"] == {"save": True, "collectionName": "cURL Import", "collectionId": "c1"}
    assert captured["headers"]["Content-Type"] == "text/plain"
    assert result == {"status": 200, "importedCount": 1}


async def test_import_postman_sends_save_as_query_param():
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["params"] = kwargs["params"]
        captured["json"] = kwargs["json"]
        return httpx.Response(200, json={"status": 200}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    collection = {"info": {"name": "My Postman Collection"}, "item": []}
    await client.import_postman(collection, save=False)

    assert captured["params"] == {"save": False}
    assert captured["json"] == collection


async def test_run_performance_bot_posts_to_run_by_id_path():
    async def fake_request(method, url, **kwargs):
        assert method == "POST"
        assert url == "https://api-dev.automationhq.ai/mtaf-core/rest/api/performance-bots/run/bot-1"
        return httpx.Response(200, json={"status": 200, "data": {"performanceMetricsId": "m-1"}}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.run_performance_bot("bot-1")

    assert result["data"]["performanceMetricsId"] == "m-1"
