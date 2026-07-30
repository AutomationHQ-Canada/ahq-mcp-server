"""
Contract tests for the non-auth discovery endpoints (/status, /tools). These sit outside the
/mcp Mount in create_app()'s routes list, so — unlike test_oauth_flow.py — no OAuth/gateway
monkeypatching is needed: nothing here ever calls out to AHQ.
"""

import types

import pytest
from starlette.testclient import TestClient

from src.http_server import create_app
from src.mcp_server import TOOLS, _HOSTED_UNSUPPORTED


def _cfg(**overrides):
    base = dict(
        ahq_base_url="https://api-dev.automationhq.ai",
        ahq_mcp_public_base_url="",  # -> http://localhost:8000
        ahq_mcp_auth_secret="test-secret",
        ahq_mcp_extra_redirect_uris="",
        ahq_mcp_max_body_bytes=2_000_000,
    )
    base.update(overrides)
    return types.SimpleNamespace(**base)


@pytest.fixture
def client():
    with TestClient(create_app(_cfg())) as c:
        yield c


def test_status_no_auth_required(client):
    resp = client.get("/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "ahq-mcp-server"
    assert "version" in body
    assert body["mode"] == "hosted"
    assert body["tool_count"] == len(TOOLS) - len(_HOSTED_UNSUPPORTED)


def test_tools_catalog_no_auth_required(client):
    resp = client.get("/tools")
    assert resp.status_code == 200
    body = resp.json()

    assert body["tools"], "expected a non-empty tool catalog"
    tool_names = {t["name"] for t in body["tools"]}
    assert tool_names.isdisjoint(_HOSTED_UNSUPPORTED)
    for tool in body["tools"]:
        assert set(tool.keys()) == {"name", "description"}

    assert body["services"], "expected a non-empty service catalog"
    for svc in body["services"]:
        assert set(svc.keys()) == {"key", "prefix"}
        assert svc["prefix"].startswith("/")


def test_mcp_still_requires_auth(client):
    resp = client.post("/mcp/", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert resp.status_code == 401
