from src.clients.base_client import BaseAhqClient
from src.config.ahq_services import MANAGED_TEST_SVC


class ManagedTestingClient(BaseAhqClient):
    """
    Handles API testing and performance testing — completely separate flow from UI bot testing.
    Used for REST/GraphQL validation, load testing, stress testing.
    """

    def __init__(self):
        super().__init__(MANAGED_TEST_SVC)

    # --- API Collections ---
    async def list_api_collections(self) -> list:
        result = await self.get("/rest/api/v2/collections")
        return result if isinstance(result, list) else result.get("content", result)

    async def get_api_collection(self, collection_id: str) -> dict:
        return await self.get(f"/rest/api/v2/collections/{collection_id}")

    # --- API Request Testing ---
    async def test_api_request(self, request_id: str, env_id: str = None) -> dict:
        payload = {"requestId": request_id}
        if env_id:
            payload["envId"] = env_id
        return await self.post("/rest/api/v2/requests/test", json=payload, timeout=60)

    # --- Performance Testing ---
    async def run_performance_test(self, collection_id: str, config: dict) -> dict:
        return await self.post(
            f"/rest/api/v2/collections/{collection_id}/performance",
            json=config,
            timeout=60,
        )

    async def get_performance_results(self, job_id: str) -> dict:
        return await self.get(f"/rest/api/jobs/{job_id}/results")

    # --- Jobs ---
    async def get_job_status(self, job_id: str) -> dict:
        return await self.get(f"/rest/api/jobs/{job_id}")

    async def list_recent_jobs(self, limit: int = 10) -> list:
        result = await self.get("/rest/api/jobs", params={"size": limit})
        return result if isinstance(result, list) else result.get("content", result)


managed_testing_client = ManagedTestingClient()
