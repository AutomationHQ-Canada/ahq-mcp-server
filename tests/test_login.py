import httpx
import pytest

from src import login
from src.clients.user_client import UserClient
from src.config.credentials import AhqCredentials


def _client(handler) -> UserClient:
    transport = httpx.MockTransport(handler)
    return UserClient(
        credentials=AhqCredentials(base_url="https://gw.example", api_token="jwt",
                                   org_id="org-1", project_id="", auth_scheme="bearer"),
        http_client=httpx.AsyncClient(transport=transport),
    )


@pytest.mark.asyncio
async def test_create_org_token_sends_the_contract_the_controller_actually_reads():
    """Lowercase organizationid/userid, and a non-empty urlDetails.

    TokenController reads `organizationid`/`userid` all-lowercase — the platform's `org-id`
    spelling everywhere else does not bind here. TokenService.validateUrlDetails throws
    "At least one microservice URL must be provided" on an empty list, and supplying baseUrl is
    what lets every later run resolve the gateway from the token itself.
    """
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = request.read().decode()
        return httpx.Response(201, json={"token": "minted", "remainingTokens": 4})

    result = await _client(handler).create_org_token(
        "org-1", "user-1", "https://gw.example", label="laptop")

    assert result["token"] == "minted"
    assert seen["url"].endswith("/rest/api/tokens/generate/org")
    assert seen["headers"]["organizationid"] == "org-1"
    assert seen["headers"]["userid"] == "user-1"
    assert seen["headers"]["expiryminutes"] == "525600"
    assert '"key": "baseUrl"' in seen["body"] or '"key":"baseUrl"' in seen["body"]
    assert "https://gw.example" in seen["body"]


def test_login_refuses_to_mint_a_second_token_without_force(tmp_path, monkeypatch, capsys):
    """The org token limit is finite and this endpoint revokes nothing it replaces."""
    env = tmp_path / ".env"
    env.write_text("TESTBOTS_API_TOKEN=already-here\n", encoding="utf-8")
    monkeypatch.setattr(login, "ENV_PATH", env)
    monkeypatch.setattr(login, "CREDENTIALS_HOME", tmp_path)

    import asyncio
    assert asyncio.run(login._run("https://gw.example", force=False)) == 1
    assert "already holds a token" in capsys.readouterr().out
    # untouched
    assert env.read_text(encoding="utf-8") == "TESTBOTS_API_TOKEN=already-here\n"


def test_write_env_replaces_both_spellings_and_keeps_unrelated_lines(tmp_path, monkeypatch):
    """A surviving AHQ_API_TOKEN would leave which credential wins down to precedence."""
    env = tmp_path / ".env"
    env.write_text(
        "AHQ_API_TOKEN=stale\nAHQ_PROJECT_ID=stale-proj\nLLM_API_KEY=keep-me\n",
        encoding="utf-8")
    monkeypatch.setattr(login, "ENV_PATH", env)
    monkeypatch.setattr(login, "CREDENTIALS_HOME", tmp_path)

    login._write_env("fresh", "proj-9", base_url=login.settings.ahq_base_url)

    written = env.read_text(encoding="utf-8")
    assert "LLM_API_KEY=keep-me" in written
    assert "TESTBOTS_API_TOKEN=fresh" in written
    assert "TESTBOTS_PROJECT_ID=proj-9" in written
    assert "stale" not in written
    # The token names its own environment; pinning it again is how an .env later points at the
    # wrong gateway.
    assert "TESTBOTS_BASE_URL" not in written


def test_write_env_pins_the_gateway_only_when_it_differs(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    monkeypatch.setattr(login, "ENV_PATH", env)
    monkeypatch.setattr(login, "CREDENTIALS_HOME", tmp_path)

    login._write_env("fresh", "proj-9", base_url="https://other.example")

    assert "TESTBOTS_BASE_URL=https://other.example" in env.read_text(encoding="utf-8")
