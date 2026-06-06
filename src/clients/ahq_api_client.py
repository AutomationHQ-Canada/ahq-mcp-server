import httpx
from src.config.ahq_services import settings


class AhqApiClient:
    def __init__(self):
        self._base_url = settings.ahq_base_url
        self._headers = {
            "Authorization": f"Bearer {settings.ahq_api_token}",
            "org-id": settings.ahq_org_id,
            "projectId": settings.ahq_project_id,
            "Content-Type": "application/json",
        }

    async def validate_token(self) -> dict:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self._base_url}/rest/api/me",
                headers=self._headers,
                timeout=10,
            )
            r.raise_for_status()
            return r.json()

    async def create_website(self, name: str, url: str) -> dict:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self._base_url}/rest/api/websites",
                headers=self._headers,
                json={"name": name, "url": url},
                timeout=30,
            )
            r.raise_for_status()
            return r.json()

    async def create_page(self, website_id: str, name: str, url: str) -> dict:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self._base_url}/rest/api/websites/{website_id}/pages",
                headers=self._headers,
                json={"name": name, "url": url},
                timeout=30,
            )
            r.raise_for_status()
            return r.json()

    async def add_locators(self, page_id: str, website_id: str, locators: list) -> dict:
        headers = {**self._headers, "websiteId": website_id}
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self._base_url}/rest/api/locators/pushSpyElements",
                headers=headers,
                json={"pageId": page_id, "elements": locators},
                timeout=60,
            )
            r.raise_for_status()
            return r.json()

    async def create_test_script(self, name: str, steps: list, page_id: str = None) -> dict:
        payload = {"name": name, "steps": steps}
        if page_id:
            payload["pageId"] = page_id
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self._base_url}/rest/api/test-scripts",
                headers=self._headers,
                json=payload,
                timeout=30,
            )
            r.raise_for_status()
            return r.json()

    async def execute_bot(self, script_id: str, env_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self._base_url}/background-jobs/execution-jobs/run-job",
                headers=self._headers,
                json={"scriptId": script_id, "envId": env_id},
                timeout=30,
            )
            r.raise_for_status()
            return r.json()

    async def get_execution_results(self, run_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self._base_url}/background-jobs/execution-jobs/{run_id}",
                headers=self._headers,
                timeout=30,
            )
            r.raise_for_status()
            return r.json()


ahq_client = AhqApiClient()
