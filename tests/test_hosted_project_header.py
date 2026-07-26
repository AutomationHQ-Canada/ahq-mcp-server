"""Hosted header-auth clients must send BOTH X-API-AUTH-KEY and projectId.

BaseAhqClient puts projectId on every AHQ request, so an empty one produces a 200 with an
empty result set rather than an error — "you have no websites" instead of "you're
misconfigured". Clients limited to a single auth header (Microsoft Copilot Studio's API-key
auth) hit this by construction, so _resolve_clients fails loudly instead.
"""

import base64
import json

import pytest
from mcp.server.lowlevel.server import request_ctx

from src.config.credentials import AhqCredentials
from src.mcp_server import _resolve_clients


def _fake_jwt(claims: dict) -> str:
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"eyJhbGciOiJub25lIn0.{payload}.fake-signature"


ORG_TOKEN = _fake_jwt({"organizationId": "org-1", "tokenType": "ORGANIZATION"})


class _FakeRequest:
    def __init__(self, headers: dict, scope: dict = None):
        self.headers = headers
        self.scope = scope or {}


class _FakeRequestContext:
    def __init__(self, request):
        self.request = request


def _with_request(request):
    return request_ctx.set(_FakeRequestContext(request))


def test_header_auth_without_project_id_fails_loudly():
    token = _with_request(_FakeRequest({"X-API-AUTH-KEY": ORG_TOKEN}))
    try:
        with pytest.raises(RuntimeError) as exc:
            _resolve_clients()
    finally:
        request_ctx.reset(token)
    assert "projectId" in str(exc.value)


def test_header_auth_with_both_headers_resolves():
    token = _with_request(
        _FakeRequest({"X-API-AUTH-KEY": ORG_TOKEN, "projectId": "proj-1"})
    )
    try:
        clients, is_hosted = _resolve_clients()
    finally:
        request_ctx.reset(token)
    assert is_hosted
    assert clients.asset._credentials.project_id == "proj-1"


def test_oauth_path_is_unaffected_by_the_header_check():
    """OAuth credentials come sealed in the Bearer token — /consent always resolves a project."""
    creds = AhqCredentials(
        base_url="https://api-dev.automationhq.ai",
        api_token=ORG_TOKEN,
        org_id="org-1",
        project_id="proj-oauth",
    )
    token = _with_request(_FakeRequest({}, scope={"ahq_credentials": creds}))
    try:
        clients, is_hosted = _resolve_clients()
    finally:
        request_ctx.reset(token)
    assert is_hosted
    assert clients.asset._credentials.project_id == "proj-oauth"
