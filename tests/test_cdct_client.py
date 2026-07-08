import httpx

from src.clients.cdct_client import CdctClient


def _client_with_fake_transport(fake_request):
    client = CdctClient()
    client._client.request = fake_request
    return client


async def test_list_consumers_sends_lowercase_org_project_headers():
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["url"] = url
        captured["headers"] = kwargs["headers"]
        return httpx.Response(200, json={"message": "ok", "status": 200, "data": [{"id": "c1", "name": "WebApp"}]}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.list_consumers()

    assert captured["url"] == "https://api-dev.automationhq.ai/mtaf-cdct/rest/api/consumers/list"
    assert captured["headers"]["organizationid"] == "test-org"
    assert captured["headers"]["projectid"] == "test-project"
    assert result == [{"id": "c1", "name": "WebApp"}]


async def test_create_contract_sends_expected_payload():
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["json"] = kwargs["json"]
        return httpx.Response(200, json={"status": 200, "data": {"id": "contract-1"}}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    await client.create_contract("consumer-1", "provider-1", "GET", contract_description="Get user by id")

    assert captured["json"] == {
        "consumerId": "consumer-1",
        "providerId": "provider-1",
        "method": "GET",
        "contractDescription": "Get user by id",
    }


async def test_run_both_tests_posts_to_combined_endpoint():
    async def fake_request(method, url, **kwargs):
        assert method == "POST"
        assert url == "https://api-dev.automationhq.ai/mtaf-cdct/rest/api/pact-runner/run-both-consumer-provider-tests/contract-1"
        return httpx.Response(200, json={"status": 200}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.run_both_tests("contract-1")

    assert result == {"status": 200}
