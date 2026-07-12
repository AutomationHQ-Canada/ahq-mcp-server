import httpx

from src.clients.config_client import ConfigClient


def _client_with_fake_transport(fake_request):
    client = ConfigClient()
    client._client.request = fake_request
    return client


async def test_add_global_parameter_preserves_existing_properties():
    # SAFETY-CRITICAL behavior under test: add_global_parameter must GET the current document and
    # merge, never send only the new property — GlobalParametersController's PUT/POST replaces the
    # entire customProperties list with whatever it receives.
    existing_doc = {
        "globalParameterId": "gp-1",
        "customProperties": [{"customPropertyId": "cp-1", "name": "api_timeout", "value": "30"}],
    }
    captured_post_body = {}

    async def fake_request(method, url, **kwargs):
        if method == "GET":
            assert url == "https://api-dev.automationhq.ai/ahq-config-services/rest/api/globalParameters"
            return httpx.Response(200, json=existing_doc, request=httpx.Request(method, url))
        assert method == "POST"
        captured_post_body.update(kwargs["json"])
        return httpx.Response(200, json={"globalParameterId": "gp-1"}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    await client.add_global_parameter("admin_email", "admin@example.com")

    names = [p["name"] for p in captured_post_body["customProperties"]]
    assert "api_timeout" in names  # existing property survived
    assert "admin_email" in names  # new property added
    assert captured_post_body["globalParameterId"] == "gp-1"


async def test_add_global_parameter_handles_empty_existing_document():
    async def fake_request(method, url, **kwargs):
        if method == "GET":
            return httpx.Response(200, json={"customProperties": []}, request=httpx.Request(method, url))
        return httpx.Response(200, json={"globalParameterId": "gp-new"}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.add_global_parameter("admin_email", "admin@example.com", description="test account")

    assert result == {"globalParameterId": "gp-new"}


async def test_search_global_parameters_sends_name_param():
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["params"] = kwargs.get("params")
        return httpx.Response(200, json=[{"name": "baseUrl", "value": "baseUrl"}], request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    await client.search_global_parameters("base")

    assert captured["params"] == {"name": "base"}


async def test_search_global_parameters_always_sends_name_param_even_when_omitted():
    # Regression test: the real endpoint's `name` @RequestParam is required server-side (no
    # required=false) — omitting the query param entirely 400s, confirmed live, even though an
    # empty string is treated as "match everything."
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["params"] = kwargs.get("params")
        return httpx.Response(200, json=[], request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    await client.search_global_parameters()

    assert captured["params"] == {"name": ""}


async def test_vault_calls_send_organizationId_header_override():
    # VaultSecretController reads "organizationId", not the "org-id" this client sends by default —
    # every vault method must pass the override explicitly.
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["headers"] = kwargs["headers"]
        return httpx.Response(200, json=[{"id": "s1", "name": "db_password"}], request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    await client.list_config_vault_secrets()

    assert "organizationId" in captured["headers"]
    assert captured["headers"]["organizationId"] == client._credentials.org_id


async def test_create_config_vault_secret_posts_expected_body():
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["json"] = kwargs["json"]
        return httpx.Response(200, json={"id": "s1"}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    await client.create_config_vault_secret("db_password", "hunter2", description="prod db")

    assert captured["method"] == "POST"
    assert captured["url"] == "https://api-dev.automationhq.ai/ahq-config-services/rest/api/vault"
    assert captured["json"] == {"name": "db_password", "value": "hunter2", "description": "prod db"}


async def test_flatten_and_delete_global_parameter_posts_to_flatten_endpoint():
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["method"] = method
        captured["url"] = url
        return httpx.Response(200, json={"deleted": True, "updatedScripts": 2}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.flatten_and_delete_global_parameter("cp-1")

    assert captured["method"] == "POST"
    assert captured["url"] == "https://api-dev.automationhq.ai/ahq-config-services/rest/api/globalParameters/custom/cp-1/flatten"
    assert result == {"deleted": True, "updatedScripts": 2}
