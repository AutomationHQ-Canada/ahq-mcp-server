"""
Slice 9d: Version Control v1 — ProjectBranchController + PullRequestController in
ahq-test-management-services. Key contract facts under test:
- branch names travel as QUERY params, never path segments (names may contain slashes)
- PR lifecycle endpoints (approve/merge/close) take NO request body
- create_branch is two-phase (NEEDS_CONFIRMATION preflight) and must surface it, not retry
- ProjectBranchRequest's Lombok `boolean isProtected` binds as JSON "protected"
"""

import httpx
import pytest
from pydantic import ValidationError

from src.clients.test_mgmt_client import TestMgmtClient
from src.mcp_server import _dispatch, DEFAULT_BUNDLE
from src.schema.asset_kinds import CommitBranchArgs, CreateBranchArgs, CreatePullRequestArgs


def _client_with_fake_transport(fake_request):
    client = TestMgmtClient()
    client._client.request = fake_request
    return client


async def _async_result(value):
    return value


class TestValidators:
    def test_create_branch_rejects_bad_strategy(self):
        with pytest.raises(ValidationError):
            CreateBranchArgs(branch_name="feature/x", strategy="MERGE")

    def test_create_branch_accepts_valid(self):
        CreateBranchArgs(branch_name="feature/x", strategy="FROM_CURRENT")

    def test_commit_rejects_blank_message(self):
        with pytest.raises(ValidationError):
            CommitBranchArgs(branch_name="feature/x", message="   ")

    def test_pr_rejects_same_source_and_target(self):
        with pytest.raises(ValidationError):
            CreatePullRequestArgs(source_branch="main", target_branch="main", title="T")


async def test_branch_name_travels_as_query_param_never_path():
    captured = []

    async def fake_request(method, url, **kwargs):
        captured.append((url, kwargs.get("params")))
        return httpx.Response(200, json={}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    await client.get_scripts_for_branch("feature/login")
    await client.commit_branch("feature/login", "checkpoint")
    await client.list_commits("feature/login")

    for url, params in captured:
        assert "feature/login" not in url  # a slashed name in the path would break routing
        assert params["branchName"] == "feature/login"


async def test_create_branch_sends_both_protected_spellings_and_confirmed():
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["json"] = kwargs.get("json")
        return httpx.Response(201, json={"status": "CREATED"}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    await client.create_branch("release/1.0", is_protected=True, confirmed=True)

    body = captured["json"]
    assert body["branchName"] == "release/1.0"
    assert body["fromBranch"] == "main"
    assert body["confirmed"] is True
    # Lombok boolean isProtected -> Jackson property "protected"
    assert body["protected"] is True
    assert body["isProtected"] is True


async def test_create_branch_surfaces_needs_confirmation_without_retry():
    call_count = 0

    async def fake_request(method, url, **kwargs):
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            200,
            json={"status": "NEEDS_CONFIRMATION", "details": "3 scripts have work on other branches"},
            request=httpx.Request(method, url),
        )

    client = _client_with_fake_transport(fake_request)
    result = await client.create_branch("feature/x")

    # exactly one call — the client must NOT auto-resend with confirmed=true
    assert call_count == 1
    assert result["status"] == "NEEDS_CONFIRMATION"


async def test_pr_lifecycle_endpoints_send_no_body():
    captured = []

    async def fake_request(method, url, **kwargs):
        captured.append((method, url, kwargs.get("json")))
        return httpx.Response(200, json={"status": "OK"}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    await client.approve_pull_request("pr-1")
    await client.merge_pull_request("pr-1")
    await client.close_pull_request("pr-1")

    for method, url, body in captured:
        assert method == "POST"
        # base_client.post normalizes None -> {}; the point is no invented payload fields
        assert body in (None, {})
    assert captured[0][1].endswith("/pull-requests/pr-1/approve")
    assert captured[1][1].endswith("/pull-requests/pr-1/merge")
    assert captured[2][1].endswith("/pull-requests/pr-1/close")


async def test_create_pull_request_body_shape():
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["json"] = kwargs.get("json")
        return httpx.Response(201, json={"prId": "pr-1", "prNumber": 7}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    await client.create_pull_request(
        "feature/login", "main", "Add login coverage",
        description="Adds the login happy path", reviewer_ids=["u1"],
    )
    body = captured["json"]
    assert body["sourceBranch"] == "feature/login"
    assert body["targetBranch"] == "main"
    assert body["title"] == "Add login coverage"
    assert body["reviewerIds"] == ["u1"]
    assert body["deleteSourceBranchAfterMerge"] is False


async def test_create_pull_request_same_branches_rejected_before_api_call():
    def _boom(*a, **kw):
        raise AssertionError("client should never be called when validation fails")

    original = DEFAULT_BUNDLE.test_mgmt.create_pull_request
    DEFAULT_BUNDLE.test_mgmt.create_pull_request = _boom
    try:
        result = await _dispatch(
            "create_pull_request",
            {"source_branch": "main", "target_branch": "main", "title": "T"},
            DEFAULT_BUNDLE, is_hosted=False,
        )
    finally:
        DEFAULT_BUNDLE.test_mgmt.create_pull_request = original
    assert "error" in result
    assert "must differ" in result["error"]


async def test_get_scripts_for_branch_dispatches_to_client():
    sentinel = [{"testScriptId": "s1"}]
    original = DEFAULT_BUNDLE.test_mgmt.get_scripts_for_branch
    DEFAULT_BUNDLE.test_mgmt.get_scripts_for_branch = lambda branch_name: _async_result(sentinel)
    try:
        result = await _dispatch(
            "get_scripts_for_branch", {"branch_name": "main"}, DEFAULT_BUNDLE, is_hosted=False
        )
    finally:
        DEFAULT_BUNDLE.test_mgmt.get_scripts_for_branch = original
    assert result == sentinel
