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


def test_login_explains_the_token_cap_instead_of_raising_the_api_error(monkeypatch, capsys):
    """The cap is the likeliest failure: per-org, only 5, and nothing revokes on replace."""
    import asyncio
    from src.clients.base_client import AhqApiError

    async def boom(*a, **k):
        raise AhqApiError(500, "Internal Server Error",
                          '{"error": "Organization has reached the maximum token limit of 5."}')

    monkeypatch.setattr(UserClient, "create_org_token", boom)
    monkeypatch.setattr(UserClient, "registration_info",
                        lambda self, email: _async({"userId": "u1", "organizationId": "org-1"}))
    monkeypatch.setattr(UserClient, "list_projects_for_user",
                        lambda self, uid: _async([{"id": "p1", "name": "Only"}]))
    monkeypatch.setattr(login, "sign_in", lambda *a, **k: _async("jwt"))
    monkeypatch.setattr(login.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *a: "someone@example.com")
    monkeypatch.setattr(login.getpass, "getpass", lambda *a: "pw")
    monkeypatch.setattr(login, "ENV_PATH", login.Path("nonexistent-for-this-test.env"))

    assert asyncio.run(login._run("https://gw.example", force=True)) == 1
    out = capsys.readouterr().out
    assert "reached its limit" in out
    assert "Administration" in out
    assert "AhqApiError" not in out


async def _async(value):
    return value


def _projects(*names):
    return [{"id": f"p{i}", "name": n} for i, n in enumerate(names)]


def test_short_project_lists_are_shown_without_asking_to_filter(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda *a: "2")
    got = login._choose(_projects("alpha", "beta", "gamma"))
    assert got["name"] == "beta"
    assert "Type part of a name" not in capsys.readouterr().out


def test_long_project_lists_are_filtered_before_being_printed(monkeypatch, capsys):
    """88 real projects, 50+ of them E2E_Project_<timestamp> fixtures, scrolled the useful
    ones off screen."""
    names = [f"E2E_Project_17714{i:05d}" for i in range(60)] + ["AHQ MASTER", "Studentink"]
    answers = iter(["Studentink", "1"])
    monkeypatch.setattr("builtins.input", lambda *a: next(answers))

    got = login._choose(_projects(*names))

    assert got["name"] == "Studentink"
    out = capsys.readouterr().out
    assert "62 projects." in out
    # the 60 fixtures must not have been printed
    assert "E2E_Project_1771400000" not in out


def test_a_typo_in_the_filter_does_not_dead_end(monkeypatch, capsys):
    names = [f"Proj{i}" for i in range(30)] + ["Studentink"]
    answers = iter(["nope", "Studentink", "1"])
    monkeypatch.setattr("builtins.input", lambda *a: next(answers))

    got = login._choose(_projects(*names))

    assert got["name"] == "Studentink"
    assert "Nothing matches 'nope'." in capsys.readouterr().out
