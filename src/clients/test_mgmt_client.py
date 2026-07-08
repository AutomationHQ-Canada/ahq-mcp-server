from src.clients.base_client import BaseAhqClient
from src.config.ahq_services import TEST_MGMT_SVC


class TestMgmtClient(BaseAhqClient):
    def __init__(self, credentials=None, http_client=None):
        super().__init__(TEST_MGMT_SVC, credentials, http_client)

    # --- Test Scripts ---
    async def list_test_scripts(self, name: str = None) -> list:
        params = {"offset": -1, "size": -1}
        if name:
            params["name"] = name
        result = await self.get("/rest/api/stories/scripts/list", params=params)
        return result.get("content", result) if isinstance(result, dict) else result

    async def get_test_script(self, script_id: str) -> dict:
        return await self.get(f"/rest/api/stories/scripts/{script_id}")

    async def create_test_script(
        self,
        name: str,
        steps: list = None,
        page_id: str = None,
        website_id: str = None,
        story_id: str = None,
        status: str = "Not Started",
        script_type: str = "WEB",
    ) -> dict:
        # websiteId is a separate field from pageId on TestScript — the UI's "Application" column
        # and its filtering key off websiteId, NOT pageId. A script with pageId but no websiteId
        # was invisible in the Table View despite existing and being correctly branch-scoped
        # (confirmed live, 2026-07-08). Likewise storyId: a script with no story attached was
        # excluded from the Table View's default "Test Scripts" listing even though the user-guide
        # documents that view as a flat list of ALL scripts — confirmed by diffing against every
        # other script in the same project, which all had a storyId.
        # status/type are plain String fields with no server-side default — sending them as JSON
        # null (i.e. omitting them) trips the UI's editor validation ("Expected string, received
        # null") when the script is opened. "Not Started"/"WEB" match real scripts in this project.
        payload = {"name": name, "testSteps": steps or [], "status": status, "type": script_type}
        if page_id:
            payload["pageId"] = page_id
        if website_id:
            payload["websiteId"] = website_id
        if story_id:
            payload["storyId"] = story_id
        return await self.post("/rest/api/stories/scripts", json=payload)

    # --- Epics ---
    async def list_epics(self) -> list:
        result = await self.get("/rest/api/epics/list", params={"offset": -1, "size": -1})
        return result.get("content", result) if isinstance(result, dict) else result

    async def get_epic(self, epic_id: str) -> dict:
        return await self.get(f"/rest/api/epics/{epic_id}")

    async def create_epic(self, name: str) -> dict:
        return await self.post("/rest/api/epics", json={"name": name})

    # --- Stories ---
    async def list_stories(self, epic_id: str) -> list:
        return await self.get(f"/rest/api/epics/{epic_id}/stories/list")

    async def create_story(self, epic_id: str, name: str) -> dict:
        return await self.post(f"/rest/api/epics/{epic_id}/stories", json={"name": name})

    # --- Test Bots ---
    async def list_bots(self, name: str = None) -> list:
        params = {"offset": -1, "size": -1}
        if name:
            params["name"] = name
        result = await self.get("/rest/api/testbots/list", params=params)
        return result.get("content", result) if isinstance(result, dict) else result

    async def get_bot(self, bot_id: str) -> dict:
        return await self.get(f"/rest/api/testbots/{bot_id}")

    # --- Test Suites ---
    async def list_suites(self) -> list:
        result = await self.get("/rest/api/suites/list", params={"offset": -1, "size": -1})
        return result.get("content", result) if isinstance(result, dict) else result

    async def create_suite(self, name: str) -> dict:
        return await self.post("/rest/api/suites", json={"name": name})

    async def add_scripts_to_suite(self, suite_id: str, script_ids: list) -> dict:
        return await self.post(f"/rest/api/suites/{suite_id}/scripts", json={"scriptIds": script_ids})

    # --- Step Templates ---
    # A TestStep's `templateId` must reference one of these — there is no static/hardcodable
    # list of action types, since templates include per-org "Common Functions" as well as
    # platform built-ins. Always resolve a real templateId before writing a step.
    async def list_templates(self, offset: int = 0) -> list:
        result = await self.get(
            f"/rest/api/templates/{self._credentials.project_id}", params={"offset": offset}
        )
        return result.get("content", result) if isinstance(result, dict) else result

    async def search_templates(self, title: str) -> list:
        # The project-scoped /rest/api/templates/{projectId}/search only returns this org's own
        # saved custom templates (often empty). Built-in action templates (Click, Navigate, ...)
        # live org/project-agnostic and only surface through the ROOT-level /search endpoint —
        # confirmed live: {projectId}/search returned [] for every built-in title, while the root
        # endpoint returned real templateIds (e.g. "Navigate" -> 21 results including
        # templateId "template-id-178"). TemplatesController.getSearchedTemplate() (root) merges
        # global built-ins with this org's Common Functions, so it's a strict superset.
        return await self.get("/rest/api/templates/search", params={"title": title})

    async def get_template(self, template_id: str) -> dict:
        return await self.get(f"/rest/api/templates/{template_id}")
