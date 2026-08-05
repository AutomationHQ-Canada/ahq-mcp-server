from src.clients.bundle import DEFAULT_BUNDLE
from src.mcp_server import _check_project_in_org

# conftest.py sets AHQ_PROJECT_ID=test-project


async def test_silent_when_project_belongs_to_org(monkeypatch):
    async def fake_list_projects():
        return [{"projectId": "test-project", "name": "The Project"}]

    monkeypatch.setattr(DEFAULT_BUNDLE.user, "list_projects", fake_list_projects)
    assert await _check_project_in_org() is None


async def test_errors_loudly_on_project_not_in_org(monkeypatch):
    async def fake_list_projects():
        return [{"projectId": "other-project", "name": "Someone Elses"}]

    monkeypatch.setattr(DEFAULT_BUNDLE.user, "list_projects", fake_list_projects)
    message = await _check_project_in_org()
    assert message.startswith("ERROR")
    assert "test-project" in message
    assert "other-project" in message  # names the valid options


async def test_accepts_id_under_plain_id_key(monkeypatch):
    async def fake_list_projects():
        return [{"id": "test-project", "name": "The Project"}]

    monkeypatch.setattr(DEFAULT_BUNDLE.user, "list_projects", fake_list_projects)
    assert await _check_project_in_org() is None


async def test_accepts_real_document_shape_underscore_id(monkeypatch):
    # The real endpoint returns `_id` + `projectName` (confirmed live 2026-07-14).
    async def fake_list_projects():
        return [{"_id": "test-project", "projectName": "The Project"}]

    monkeypatch.setattr(DEFAULT_BUNDLE.user, "list_projects", fake_list_projects)
    assert await _check_project_in_org() is None


async def test_network_failure_downgrades_to_warning(monkeypatch):
    async def fake_list_projects():
        raise RuntimeError("connect timeout")

    monkeypatch.setattr(DEFAULT_BUNDLE.user, "list_projects", fake_list_projects)
    message = await _check_project_in_org()
    assert message.startswith("WARNING")


def test_list_my_projects_degrades_instead_of_surfacing_a_500():
    """/users/me 500s for an ORGANIZATION token, which made the friendly guard unreachable.

    The tool exists to disambiguate between several projects. A credential that names no user
    has nothing to disambiguate, so that is an empty result with an explanation -- not an error.
    """
    import asyncio
    from unittest.mock import AsyncMock, MagicMock
    import src.mcp_server as m
    from src.clients.base_client import AhqApiError

    clients = MagicMock()
    clients.user.get_current_user = AsyncMock(
        side_effect=AhqApiError(500, "Internal Server Error", '{"message":"No value present"}'))

    result = asyncio.run(m._dispatch("list_my_projects", {}, clients))

    assert result["projects"] == []
    assert "error" not in result
    assert "ORGANIZATION" in result["note"]
