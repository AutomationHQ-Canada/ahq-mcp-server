"""
Fixes from the third field report: an edit landing on the wrong branch, an execution accepted
with ids that no longer exist, and a credentialed crawl that never captured the login form.

All three shared a shape — the platform accepts the call, so nothing surfaces until minutes
later (or not at all), and the model reports success. These tests pin the point where each one
now becomes visible instead.
"""
from types import SimpleNamespace

import pytest

from src import mcp_server
from src.clients.test_mgmt_client import TestMgmtClient


# --- the edit that landed on somebody else's branch ---------------------------------------

def _script_client(monkeypatch, ambient_branch: str):
    """A client whose GET reports `ambient_branch`, the way the real API does."""
    client = TestMgmtClient()
    puts = []

    async def fake_get(path, **kwargs):
        return {"testScriptId": "s1", "name": "S", "testSteps": [],
                "currentBranchName": ambient_branch}

    async def fake_put(path, json=None, **kwargs):
        puts.append(json)
        return {"message": "Test script updated successfully"}

    monkeypatch.setattr(client, "get", fake_get)
    monkeypatch.setattr(client, "put", fake_put)
    return client, puts


async def test_add_test_steps_pins_the_branch_it_was_given(monkeypatch):
    """The whole bug: the GET's branch is the caller's ambient one, not the script's."""
    client, puts = _script_client(monkeypatch, ambient_branch="feature/somebody-else")
    await client.add_test_steps("s1", [{"templateId": "t"}], branch_name="main")
    assert puts[0]["currentBranchName"] == "main"


async def test_update_test_script_pins_the_branch_it_was_given(monkeypatch):
    client, puts = _script_client(monkeypatch, ambient_branch="feature/somebody-else")
    await client.update_test_script("s1", branch_name="main", name="renamed")
    assert puts[0]["currentBranchName"] == "main"
    assert puts[0]["name"] == "renamed"


async def test_the_landing_branch_comes_back_even_when_unpinned(monkeypatch):
    """Without this the drift is invisible: success is reported either way.

    A caller that doesn't pass branch_name still gets told where the write went, which is the
    only signal that a later execute_bot is about to run a different version than the one just
    edited.
    """
    client, _ = _script_client(monkeypatch, ambient_branch="feature/rajesh")
    result = await client.add_test_steps("s1", [{"templateId": "t"}])
    assert result["branchName"] == "feature/rajesh"


# --- the execution accepted with ids that no longer exist ----------------------------------

def _bundle(grids=None, environments=None, branches=None):
    async def _listing(value):
        if isinstance(value, Exception):
            raise value
        return value

    return SimpleNamespace(
        config=SimpleNamespace(
            list_grids=lambda: _listing(grids if grids is not None else []),
            list_environments=lambda: _listing(environments if environments is not None else []),
        ),
        test_mgmt=SimpleNamespace(
            list_branches=lambda: _listing(branches if branches is not None else []),
        ),
    )


GOOD_CONFIG = {"gridId": "g1", "baseUrl": "e1", "targetBranchName": "main"}
KNOWN = {
    "grids": [{"gridId": "g1", "name": "AHQ Premium Grid"}],
    "environments": [{"id": "e1", "name": "dev"}],
    "branches": [{"branchName": "main"}],
}


async def test_a_grid_that_no_longer_exists_is_refused_before_the_run():
    """The reported failure: a grid id recalled from an earlier session, deleted since.

    It cost a full execution cycle and surfaced as `gridUrlForExecution is null` minutes in.
    """
    result = await mcp_server._preflight_execution_configuration(
        _bundle(**KNOWN), {**GOOD_CONFIG, "gridId": "deleted-grid"},
    )
    assert "deleted-grid" in result["error"]
    assert "AHQ Premium Grid (g1)" in result["error"], "must name the real grids, not just refuse"


async def test_a_raw_url_in_baseurl_is_refused_before_the_run():
    """baseUrl is an environment id despite the name; a URL there kills the run at report time."""
    result = await mcp_server._preflight_execution_configuration(
        _bundle(**KNOWN), {**GOOD_CONFIG, "baseUrl": "https://app.example.com"},
    )
    assert "Environment id" in result["error"]


async def test_an_unknown_branch_is_refused_before_the_run():
    result = await mcp_server._preflight_execution_configuration(
        _bundle(**KNOWN), {**GOOD_CONFIG, "targetBranchName": "mian"},
    )
    assert "mian" in result["error"]


async def test_a_fully_valid_configuration_passes():
    assert await mcp_server._preflight_execution_configuration(_bundle(**KNOWN), GOOD_CONFIG) is None


@pytest.mark.parametrize("broken", ["grids", "environments", "branches"])
async def test_the_check_never_becomes_the_failure(broken):
    """Fail-open, deliberately.

    A lookup this server can't complete (permissions, an endpoint that moved, a flaky gateway)
    must not be the reason a run the user asked for can't start — the platform would have
    accepted it. Same discipline as create_test_script's branch check.
    """
    lists = {**KNOWN, broken: RuntimeError("gateway said no")}
    assert await mcp_server._preflight_execution_configuration(_bundle(**lists), GOOD_CONFIG) is None


async def test_an_empty_listing_is_treated_as_unverifiable_not_as_all_invalid():
    """An empty list is far more likely a wrong-project token than a project with zero grids."""
    assert await mcp_server._preflight_execution_configuration(_bundle(), GOOD_CONFIG) is None


# --- the login form the credentialed crawl threw away --------------------------------------

class _FakePage:
    def __init__(self, url):
        self.url = url

    async def title(self):
        return "Sign in"


async def test_capture_page_reports_the_url_it_landed_on(monkeypatch):
    """add_locators upserts by page URL, so a redirect must not misfile the locators."""
    from src.tools import crawl_url as mod

    async def fake_extract(page):
        return [{"name": "Email input", "css": "#email"}]

    async def fake_validate(page, locators):
        return locators

    monkeypatch.setattr(mod, "_extract_locators", fake_extract)
    monkeypatch.setattr(mod, "_validate_locators", fake_validate)

    captured = await mod._capture_page(_FakePage("https://app.example.com/asked"),
                                       "https://app.example.com/landed")
    assert captured["url"] == "https://app.example.com/landed"
    assert captured["total_valid"] == 1
    assert captured["passes_threshold"] is True
