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
