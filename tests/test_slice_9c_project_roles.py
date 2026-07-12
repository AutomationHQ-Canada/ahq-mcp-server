"""
Slice 9c: Project Roles — ProjectRoleController in ahq-test-management-services,
base /rest/api/projects/{projectId}/roles, standard org-id header.
"""

import httpx
import pytest
from pydantic import ValidationError

from src.clients.test_mgmt_client import TestMgmtClient
from src.mcp_server import _dispatch, DEFAULT_BUNDLE
from src.schema.asset_kinds import (
    AssignRoleArgs,
    ProjectRoleCreateArgs,
    ProjectRoleUpdateArgs,
)


def _client_with_fake_transport(fake_request):
    client = TestMgmtClient()
    client._client.request = fake_request
    return client


async def _async_result(value):
    return value


class TestValidators:
    def test_accepts_valid_permissions(self):
        ProjectRoleCreateArgs(role_name="Reviewer", permissions=["VIEW", "EXECUTE"])

    def test_rejects_unknown_permission(self):
        with pytest.raises(ValidationError):
            ProjectRoleCreateArgs(role_name="Reviewer", permissions=["VIEW", "ADMIN"])

    def test_rejects_empty_permissions(self):
        with pytest.raises(ValidationError):
            ProjectRoleCreateArgs(role_name="Reviewer", permissions=[])

    def test_update_rejects_unknown_permission(self):
        with pytest.raises(ValidationError):
            ProjectRoleUpdateArgs(role_id="r1", permissions=["READ"])

    def test_assign_rejects_blank_user_id(self):
        with pytest.raises(ValidationError):
            AssignRoleArgs(role_id="r1", user_id="  ")


async def test_roles_endpoints_use_project_id_in_path():
    captured = []

    async def fake_request(method, url, **kwargs):
        captured.append((method, url, kwargs.get("json")))
        return httpx.Response(200, json=[], request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    project_id = client._credentials.project_id

    await client.list_project_roles()
    await client.update_project_role_permissions("role-1", ["VIEW"])
    await client.list_project_members()

    assert captured[0][1].endswith(f"/rest/api/projects/{project_id}/roles")
    assert captured[1][1].endswith(f"/rest/api/projects/{project_id}/roles/role-1")
    # update body carries ONLY permissions — role name is immutable server-side and the endpoint
    # ignores anything else, so nothing else may be sent (no accidental rename attempts)
    assert captured[1][2] == {"permissions": ["VIEW"]}
    assert captured[2][1].endswith(f"/rest/api/projects/{project_id}/roles/members")


async def test_create_role_sends_both_default_spellings():
    # CreateRoleRequest's Lombok-generated property name for `boolean isDefault` is "default" —
    # sending only "isDefault" would silently bind false. Both spellings are sent.
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["json"] = kwargs.get("json")
        return httpx.Response(201, json={"roleId": "r1"}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    await client.create_project_role("Reviewer", ["VIEW", "EXECUTE"], is_default=True)

    assert captured["json"]["roleName"] == "Reviewer"
    assert captured["json"]["permissions"] == ["VIEW", "EXECUTE"]
    assert captured["json"]["default"] is True
    assert captured["json"]["isDefault"] is True


async def test_create_project_role_invalid_permission_rejected_before_api_call():
    def _boom(*a, **kw):
        raise AssertionError("client should never be called when validation fails")

    original = DEFAULT_BUNDLE.test_mgmt.create_project_role
    DEFAULT_BUNDLE.test_mgmt.create_project_role = _boom
    try:
        result = await _dispatch(
            "create_project_role",
            {"role_name": "Reviewer", "permissions": ["SUPERUSER"]},
            DEFAULT_BUNDLE, is_hosted=False,
        )
    finally:
        DEFAULT_BUNDLE.test_mgmt.create_project_role = original
    assert "error" in result
    assert "SUPERUSER" in result["error"]


async def test_assign_project_role_dispatches_to_client():
    captured = {}

    def fake(role_id, user_id):
        captured["role_id"] = role_id
        captured["user_id"] = user_id
        return _async_result({"userId": user_id, "roleId": role_id})

    original = DEFAULT_BUNDLE.test_mgmt.assign_project_role
    DEFAULT_BUNDLE.test_mgmt.assign_project_role = fake
    try:
        result = await _dispatch(
            "assign_project_role", {"role_id": "r1", "user_id": "u1"}, DEFAULT_BUNDLE, is_hosted=False
        )
    finally:
        DEFAULT_BUNDLE.test_mgmt.assign_project_role = original
    assert result == {"userId": "u1", "roleId": "r1"}
    assert captured == {"role_id": "r1", "user_id": "u1"}
