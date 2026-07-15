import types

import pytest

import src.mcp_server as mcp_server
from src.clients.bundle import DEFAULT_BUNDLE
from src.config.credentials import AhqCredentials
from src.hosted.rate_limit import OrgRateLimiter
from src.mcp_server import _HOSTED_UNSUPPORTED, _dispatch, _dispatch_hosted


def _fake_clients(org="org-1", project="proj-1"):
    creds = AhqCredentials(base_url="https://x", api_token="t", org_id=org, project_id=project)
    return types.SimpleNamespace(user=types.SimpleNamespace(_credentials=creds))


@pytest.fixture
def captured_audit(monkeypatch):
    lines = []

    def fake_audit(event, **fields):
        lines.append({"event": event, **fields})

    monkeypatch.setattr(mcp_server, "audit_log", fake_audit)
    return lines


async def test_tool_call_audit_line_has_fields_and_never_args(monkeypatch, captured_audit):
    async def fake_dispatch(name, args, clients, is_hosted=False):
        return {"ok": True}

    monkeypatch.setattr(mcp_server, "_dispatch", fake_dispatch)
    monkeypatch.setattr(mcp_server, "_rate_limiter", OrgRateLimiter(60))

    secret_args = {"password": "hunter2", "steps": [{"value": "s3cret"}]}
    await _dispatch_hosted("create_test_script", secret_args, _fake_clients())

    assert len(captured_audit) == 1
    line = captured_audit[0]
    assert line["event"] == "tool_call"
    assert line["org"] == "org-1"
    assert line["project"] == "proj-1"
    assert line["tool"] == "create_test_script"
    assert line["ok"] is True
    assert isinstance(line["duration_ms"], int)
    assert "hunter2" not in str(line)
    assert "s3cret" not in str(line)


async def test_audit_line_on_dispatch_exception(monkeypatch, captured_audit):
    async def boom(name, args, clients, is_hosted=False):
        raise RuntimeError("gateway 502")

    monkeypatch.setattr(mcp_server, "_dispatch", boom)
    monkeypatch.setattr(mcp_server, "_rate_limiter", OrgRateLimiter(60))

    with pytest.raises(RuntimeError):
        await _dispatch_hosted("list_websites", {}, _fake_clients())
    assert captured_audit[0]["ok"] is False
    assert "gateway 502" in captured_audit[0]["error"]


async def test_rate_limited_call_returns_clean_error(monkeypatch, captured_audit):
    limiter = OrgRateLimiter(1)
    monkeypatch.setattr(mcp_server, "_rate_limiter", limiter)

    async def fake_dispatch(name, args, clients, is_hosted=False):
        return {"ok": True}

    monkeypatch.setattr(mcp_server, "_dispatch", fake_dispatch)

    assert await _dispatch_hosted("list_websites", {}, _fake_clients()) == {"ok": True}
    second = await _dispatch_hosted("list_websites", {}, _fake_clients())
    assert "Rate limit exceeded" in second["error"]


async def test_crawl_url_no_longer_hosted_blocked(monkeypatch):
    assert "crawl_url" not in _HOSTED_UNSUPPORTED

    captured = {}

    async def fake_crawl(url, credentials=None, max_pages=20, hosted=False):
        captured["hosted"] = hosted
        return {"pages_crawled": 0}

    monkeypatch.setattr(mcp_server, "_crawl_url", fake_crawl)
    result = await _dispatch("crawl_url", {"url": "https://example.com"}, DEFAULT_BUNDLE, is_hosted=True)
    assert "error" not in result
    assert captured["hosted"] is True


async def test_extract_requirements_still_hosted_blocked():
    assert "extract_requirements" in _HOSTED_UNSUPPORTED
    result = await _dispatch("extract_requirements", {"file_path": "x"}, DEFAULT_BUNDLE, is_hosted=True)
    assert "not available" in result["error"]


async def test_check_local_agent_status_still_hosted_blocked():
    result = await _dispatch("check_local_agent_status", {}, DEFAULT_BUNDLE, is_hosted=True)
    assert "not available" in result["error"]
