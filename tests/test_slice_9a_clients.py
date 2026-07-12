"""
Client-level tests for Slice 9a: Recorded Script + Common Function CRUD.

The safety-critical behavior under test is update_common_function's GET-merge-PUT:
the real PUT /rest/api/commonFunctions/{id} is a full-document replace
(commonFunctionRepo.save(requestBody)) that does not preserve ANY field from the existing
document — not even organizationId/projectId. A partial body wipes testSteps/parameters/
returnType and orphans the function from its org. This is the bug class behind the real
User Test Step rename incident (2026-07-09).
"""

import httpx
import pytest

from src.clients.asset_client import AssetClient
from src.clients.test_mgmt_client import TestMgmtClient


def _asset_client_with_fake_transport(fake_request):
    client = AssetClient()
    client._client.request = fake_request
    return client


def _test_mgmt_client_with_fake_transport(fake_request):
    client = TestMgmtClient()
    client._client.request = fake_request
    return client


# ---------------------------------------------------------------------------
# Common Functions
# ---------------------------------------------------------------------------

EXISTING_CF = {
    "commonFunctionId": "cf-1",
    "organizationId": "org-1",
    "projectId": "proj-1",
    "name": "Old Name",
    "description": "does a thing",
    "status": "READY",
    "websiteId": "w-1",
    "returnType": {"name": "", "type": "String", "array": False},
    "testSteps": [
        {"templateId": "template-id-4", "templateTitle": "Click {{ui-locator}}", "sequence": 1,
         "parameters": [{"key": "ui-locator", "value": {"locatorId": "loc-1"}}]},
    ],
    "parameters": [{"name": "username", "type": "String", "array": False}],
}


async def test_update_common_function_rename_preserves_everything_else():
    captured_put_body = {}

    async def fake_request(method, url, **kwargs):
        if method == "GET":
            return httpx.Response(200, json=EXISTING_CF, request=httpx.Request(method, url))
        assert method == "PUT"
        captured_put_body.update(kwargs["json"])
        return httpx.Response(200, json={"message": "Success", "id": "cf-1"}, request=httpx.Request(method, url))

    client = _asset_client_with_fake_transport(fake_request)
    await client.update_common_function("cf-1", name="New Name")

    assert captured_put_body["name"] == "New Name"
    # THE point of this slice: everything not being changed survives the full-replace PUT
    assert captured_put_body["testSteps"] == EXISTING_CF["testSteps"]
    assert captured_put_body["parameters"] == EXISTING_CF["parameters"]
    assert captured_put_body["returnType"] == EXISTING_CF["returnType"]
    assert captured_put_body["organizationId"] == "org-1"
    assert captured_put_body["projectId"] == "proj-1"
    assert captured_put_body["websiteId"] == "w-1"
    assert captured_put_body["status"] == "READY"


async def test_update_common_function_refuses_to_write_back_masked_encrypted_value():
    # CommonFunctionController.getById masks encrypted-template literal values (type 0) as
    # all-asterisks on every read. Blindly PUTting the fetched document back would therefore
    # permanently replace the real stored password with "********". The client must refuse
    # unless the caller supplies replacement testSteps.
    masked_cf = dict(EXISTING_CF)
    masked_cf["testSteps"] = [
        {"templateId": "template-id-105",
         "templateTitle": "Enter encrypted text {{password}} for {{ui-locator}}",
         "sequence": 1,
         "parameters": [
             {"key": "password", "value": {"type": 0, "value": "********"}},
             {"key": "ui-locator", "value": {"locatorId": "loc-1"}},
         ]},
    ]
    put_called = False

    async def fake_request(method, url, **kwargs):
        nonlocal put_called
        if method == "GET":
            return httpx.Response(200, json=masked_cf, request=httpx.Request(method, url))
        put_called = True
        return httpx.Response(200, json={}, request=httpx.Request(method, url))

    client = _asset_client_with_fake_transport(fake_request)
    with pytest.raises(ValueError, match="masks"):
        await client.update_common_function("cf-1", name="New Name")
    assert not put_called


async def test_update_common_function_allows_masked_doc_when_caller_replaces_steps():
    masked_cf = dict(EXISTING_CF)
    masked_cf["testSteps"] = [
        {"templateId": "template-id-105",
         "templateTitle": "Enter encrypted text {{password}} for {{ui-locator}}",
         "sequence": 1,
         "parameters": [{"key": "password", "value": {"type": 0, "value": "****"}}]},
    ]
    new_steps = [
        {"templateId": "template-id-105",
         "templateTitle": "Enter encrypted text {{password}} for {{ui-locator}}",
         "sequence": 1,
         # vault reference (type 7) — not masked, and the right way to store a credential anyway
         "parameters": [{"key": "password", "value": {"type": 7, "value": "login-password"}}]},
    ]
    captured_put_body = {}

    async def fake_request(method, url, **kwargs):
        if method == "GET":
            return httpx.Response(200, json=masked_cf, request=httpx.Request(method, url))
        captured_put_body.update(kwargs["json"])
        return httpx.Response(200, json={}, request=httpx.Request(method, url))

    client = _asset_client_with_fake_transport(fake_request)
    await client.update_common_function("cf-1", testSteps=new_steps)
    assert captured_put_body["testSteps"] == new_steps


async def test_update_common_function_vault_type_values_do_not_trip_the_mask_guard():
    # A type-7 (vault) value is returned as-is by the server — even if the secret NAME happens
    # to be asterisks-like it isn't the mask pattern; more importantly type != 0 must not block.
    cf = dict(EXISTING_CF)
    cf["testSteps"] = [
        {"templateId": "template-id-105",
         "templateTitle": "Enter encrypted text {{password}} for {{ui-locator}}",
         "sequence": 1,
         "parameters": [{"key": "password", "value": {"type": 7, "value": "login-password"}}]},
    ]
    put_called = False

    async def fake_request(method, url, **kwargs):
        nonlocal put_called
        if method == "GET":
            return httpx.Response(200, json=cf, request=httpx.Request(method, url))
        put_called = True
        return httpx.Response(200, json={}, request=httpx.Request(method, url))

    client = _asset_client_with_fake_transport(fake_request)
    await client.update_common_function("cf-1", name="New Name")
    assert put_called


async def test_list_common_functions_always_sends_offset():
    # CommonFunctionController.list is mapped with params="offset" — without the offset query
    # param NO handler matches the route at all (it's a routing key, not just a paging default).
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["params"] = kwargs.get("params")
        return httpx.Response(200, json={"content": []}, request=httpx.Request(method, url))

    client = _asset_client_with_fake_transport(fake_request)
    await client.list_common_functions()
    assert "offset" in captured["params"]


async def test_create_common_function_sends_full_document_shape():
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["json"] = kwargs.get("json")
        return httpx.Response(200, json={"message": "Success", "id": "cf-new"}, request=httpx.Request(method, url))

    client = _asset_client_with_fake_transport(fake_request)
    await client.create_common_function(
        "Login helper", "w-1", "READY", {"name": "", "type": "String", "array": False}
    )
    body = captured["json"]
    assert body["name"] == "Login helper"
    assert body["websiteId"] == "w-1"
    assert body["status"] == "READY"
    assert body["returnType"]["type"] == "String"
    # omitted optionals become empty collections, never absent/null (entity defaults are empty)
    assert body["testSteps"] == []
    assert body["parameters"] == []


# ---------------------------------------------------------------------------
# Recorded Scripts
# ---------------------------------------------------------------------------

async def test_recorded_script_calls_send_organizationId_header():
    # RecordedScriptController reads @RequestHeader("organizationId") — unlike every other
    # controller in the same service, which reads "org-id". The client must add it per call.
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["headers"] = kwargs.get("headers")
        return httpx.Response(200, json={"content": []}, request=httpx.Request(method, url))

    client = _test_mgmt_client_with_fake_transport(fake_request)
    await client.list_recorded_scripts()
    assert "organizationId" in captured["headers"]
    assert captured["headers"]["organizationId"] == client._credentials.org_id


async def test_promote_recorded_script_sends_storyId_as_query_param_and_branch_in_body():
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["url"] = url
        captured["params"] = kwargs.get("params")
        captured["json"] = kwargs.get("json")
        captured["headers"] = kwargs.get("headers")
        return httpx.Response(
            200,
            json={"status": 200, "testScriptId": "ts-1"},
            request=httpx.Request(method, url),
        )

    client = _test_mgmt_client_with_fake_transport(fake_request)
    await client.promote_recorded_script("rs-1", "story-1", name="Promoted Script")

    assert captured["url"].endswith("/rest/api/recorded-scripts/rs-1/promote")
    # storyId is a QUERY PARAM on the real controller, not a body field
    assert captured["params"] == {"storyId": "story-1"}
    # branch is always explicit — ambient checked-out-branch fallback is unstable
    assert captured["json"]["currentBranchName"] == "main"
    assert captured["json"]["name"] == "Promoted Script"
    assert captured["headers"]["organizationId"] == client._credentials.org_id
