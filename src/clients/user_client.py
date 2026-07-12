from src.clients.base_client import BaseAhqClient
from src.config.ahq_services import USER_MGMT_SVC

# Archive Manager entity -> route prefix. All *ArchiveController classes live in
# ahq-user-management-services (confirmed against the real controllers, not just the frontend's
# folder naming) and extend one generic ArchiveController<T, ID> with a uniform contract:
#   GET  {prefix}/archived?page=&size=&search=   (organizationId+projectId headers)
#   POST {prefix}/{id}/archive                    (body: {"archiveReason": ...}, optional)
#   POST {prefix}/{id}/restore
#   DELETE {prefix}/{id}/permanent
# EXCEPTION — "locator": LocatorArchiveController does NOT extend the base class; its list is a
# GET on the prefix root (no /archived suffix) and permanent delete is DELETE /{id} (no
# /permanent suffix). There is no locator archive action at all (locators land in the archive as
# a side-effect of page/website deletion elsewhere).
# NOT HERE — "recorded_script": its archive endpoints live on RecordedScriptController in
# ahq-test-management-services; the dispatcher routes that entity to TestMgmtClient instead.
ARCHIVE_ENTITY_PATHS = {
    "epic": "/api/epics",
    "story": "/api/stories",
    "website": "/api/websites",
    "page": "/api/pages",
    "locator": "/api/archived-locators",
    "test_script": "/api/test-scripts",
    "test_suite": "/api/test-suites",
    "test_bot": "/api/test-bots",
    "test_bot_folder": "/api/testbot-folders",
}


class UserClient(BaseAhqClient):
    def __init__(self, credentials=None, http_client=None):
        super().__init__(USER_MGMT_SVC, credentials, http_client)

    async def get_current_user(self) -> dict:
        return await self.get("/rest/api/users/me")

    async def list_projects(self) -> list:
        result = await self.get("/rest/api/projects")
        return result if isinstance(result, list) else result.get("content", result)

    async def list_users(self) -> list:
        result = await self.get("/rest/api/users")
        return result if isinstance(result, list) else result.get("content", result)

    # --- Archive Manager ---
    # The generic ArchiveController reads @RequestHeader("organizationId") — the third controller
    # family found using that spelling instead of the default "org-id" (after RecordedScript and
    # the config-services vault).
    def _archive_headers(self) -> dict:
        return {"organizationId": self._credentials.org_id}

    async def list_archived(self, entity_type: str, search: str = None, page: int = 0, size: int = 50) -> dict:
        base = ARCHIVE_ENTITY_PATHS[entity_type]
        path = base if entity_type == "locator" else f"{base}/archived"
        params = {"page": page, "size": size}
        if search:
            params["search"] = search
        return await self.get(path, params=params, extra_headers=self._archive_headers())

    async def restore_archived(self, entity_type: str, asset_id: str) -> dict:
        base = ARCHIVE_ENTITY_PATHS[entity_type]
        return await self.post(f"{base}/{asset_id}/restore", extra_headers=self._archive_headers())

    async def permanently_delete_archived(self, entity_type: str, asset_id: str) -> dict:
        base = ARCHIVE_ENTITY_PATHS[entity_type]
        suffix = "" if entity_type == "locator" else "/permanent"
        return await self.delete(f"{base}/{asset_id}{suffix}", extra_headers=self._archive_headers())
