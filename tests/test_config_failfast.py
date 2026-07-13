"""
Guards against the silent-misconfiguration failure mode found during the first teammate plugin
install (2026-07-13): the server started with no .env (cwd-relative lookup missed the plugin
root), so every tool "succeeded" against the web frontend's HTML instead of the API.
"""
import httpx
import pytest

import src.mcp_server as mcp_server
from src.clients.base_client import AhqApiError, BaseAhqClient
from src.config.ahq_services import REPO_ROOT, Settings


def _client_with_fake_transport(fake_request):
    client = BaseAhqClient("/svc")
    client._client.request = fake_request
    return client


async def test_html_response_raises_instead_of_masquerading_as_success():
    async def fake_request(method, url, **kwargs):
        return httpx.Response(
            200, text="<!DOCTYPE html><html><head><title>AutomationHQ</title></head></html>",
            headers={"content-type": "text/html"}, request=httpx.Request(method, url),
        )

    client = _client_with_fake_transport(fake_request)
    with pytest.raises(AhqApiError) as exc_info:
        await client.get("/rest/api/websites")
    assert "AHQ_BASE_URL" in str(exc_info.value)


async def test_non_json_non_html_body_still_returned_verbatim():
    async def fake_request(method, url, **kwargs):
        return httpx.Response(200, text="plain text pong", request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.get("/ping")
    assert result == {"status": 200, "body": "plain text pong"}


def test_require_stdio_config_raises_when_token_missing(monkeypatch):
    monkeypatch.setattr(mcp_server.settings, "ahq_api_token", "")
    with pytest.raises(RuntimeError) as exc_info:
        mcp_server._require_stdio_config()
    msg = str(exc_info.value)
    assert "AHQ_API_TOKEN" in msg
    assert ".env" in msg  # points at the expected file, not just "misconfigured"


def test_require_stdio_config_passes_with_full_config():
    # conftest.py sets all three env vars, so the ambient settings are complete
    mcp_server._require_stdio_config()


def test_env_file_is_resolved_from_repo_root_not_cwd():
    env_files = Settings.model_config["env_file"]
    assert str(REPO_ROOT / ".env") in env_files
    assert env_files[-1] == ".env"  # cwd stays available as the highest-precedence override
    assert (REPO_ROOT / "pyproject.toml").exists()  # sanity: parents[2] really is the repo root


def test_stable_home_env_is_lowest_precedence_candidate():
    # ~/.ahq/.env survives plugin upgrades (each version = fresh folder); it must be FIRST in
    # the tuple so any version-local .env still overrides it (pydantic: later files win).
    from pathlib import Path

    env_files = Settings.model_config["env_file"]
    assert env_files[0] == str(Path.home() / ".ahq" / ".env")


def test_base_url_has_no_default(monkeypatch):
    # The old default (the web frontend URL) was never a working value; absence must mean empty.
    for var in ("AHQ_BASE_URL", "AHQ_API_TOKEN", "AHQ_PROJECT_ID"):
        monkeypatch.delenv(var, raising=False)
    s = Settings(_env_file=None)
    assert s.ahq_base_url == ""
