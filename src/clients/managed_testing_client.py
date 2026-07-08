from src.clients.base_client import BaseAhqClient
from src.config.ahq_services import MANAGED_TEST_SVC


def _unwrap(result):
    """mtaf-core list responses wrap items in a `data` field (not `content` like the UI-test services)."""
    return result.get("data", result) if isinstance(result, dict) else result


class ManagedTestingClient(BaseAhqClient):
    """
    Handles API testing and performance testing (mtaf-core) — a separate flow from UI bot testing,
    used for REST/GraphQL request validation, chained-workflow testing, and JMeter-backed load testing.
    """

    def __init__(self):
        super().__init__(MANAGED_TEST_SVC)

    # --- API Collections v2 ---
    async def list_api_collections(self) -> list:
        return _unwrap(await self.get("/rest/api/v2/collections/list"))

    async def get_api_collection(self, collection_id: str) -> dict:
        return await self.get(f"/rest/api/v2/collections/{collection_id}")

    async def create_api_collection(self, name: str, description: str = None, variables: list = None) -> dict:
        payload = {"name": name}
        if description:
            payload["description"] = description
        if variables:
            payload["variables"] = variables
        return await self.post("/rest/api/v2/collections", json=payload)

    # --- API Requests v2 ---
    async def list_api_requests(self) -> list:
        return _unwrap(await self.get("/rest/api/v2/requests/list"))

    async def get_api_request(self, request_id: str) -> dict:
        return await self.get(f"/rest/api/v2/requests/{request_id}")

    async def create_api_request(
        self,
        name: str,
        method: str,
        url: str,
        collection_id: str = None,
        query_params: list = None,
        header_params: list = None,
        body_params=None,
    ) -> dict:
        payload = {"name": name, "method": method, "url": url}
        if collection_id:
            payload["collectionId"] = collection_id
        if query_params:
            payload["queryParams"] = query_params
        if header_params:
            payload["headerParams"] = header_params
        if body_params is not None:
            payload["bodyParams"] = body_params
        return await self.post("/rest/api/v2/requests", json=payload)

    async def test_api_request(
        self, request: dict, variables: dict = None, data_row: dict = None, environment: str = None
    ) -> dict:
        payload = {
            "request": request,
            "variables": variables or {},
            "dataRow": data_row or {},
        }
        if environment:
            payload["environment"] = environment
        return await self.post("/rest/api/v2/requests/test", json=payload, timeout=60)

    # --- Import ---
    async def import_curl(
        self, commands: str, save: bool = True, collection_name: str = "cURL Import", collection_id: str = None
    ) -> dict:
        params = {"save": save, "collectionName": collection_name}
        if collection_id:
            params["collectionId"] = collection_id
        # base_client.post() always sends a json body — curl import needs a raw text/plain body instead.
        return await self._request(
            "POST",
            f"{self._base}/rest/api/v2/import/curl",
            params=params,
            content=commands,
            extra_headers={"Content-Type": "text/plain"},
            timeout=30,
        )

    async def import_postman(self, collection: dict, save: bool = True) -> dict:
        return await self.post(
            "/rest/api/v2/import/postman", json=collection, params={"save": save}, timeout=30
        )

    # --- Workflows ---
    async def list_workflows(self) -> list:
        return _unwrap(await self.get("/rest/api/workflows/list"))

    async def get_workflow(self, workflow_id: str) -> dict:
        return await self.get(f"/rest/api/workflows/list/{workflow_id}")

    async def create_workflow(self, name: str, description: str = None, workflow_list: list = None) -> dict:
        payload = {"name": name, "workflowList": workflow_list or []}
        if description:
            payload["description"] = description
        return await self.post("/rest/api/workflows", json=payload)

    async def test_workflow(
        self, name: str, api_requests: list, description: str = None, load_ratio: float = None
    ) -> dict:
        payload = {"name": name, "apiRequests": api_requests}
        if description:
            payload["description"] = description
        if load_ratio:
            payload["loadRatio"] = load_ratio
        return await self.post("/rest/api/workflows/test", json=payload, timeout=60)

    # --- Performance Bots ---
    async def list_performance_bots(self) -> list:
        return _unwrap(await self.get("/rest/api/performance-bots/list"))

    async def get_performance_bot(self, bot_id: str) -> dict:
        return await self.get(f"/rest/api/performance-bots/{bot_id}")

    async def run_performance_bot(self, bot_id: str) -> dict:
        return await self.post(f"/rest/api/performance-bots/run/{bot_id}")

    async def stop_performance_bot(self, bot_id: str) -> dict:
        return await self.post(f"/rest/api/performance-bots/stop/{bot_id}")

    async def get_performance_results(self, metrics_id: str, polling: bool = True) -> dict:
        return await self.get(
            f"/rest/api/performance-metrics/results/{metrics_id}", params={"polling": str(polling).lower()}
        )

    # --- Vault Secrets v2 ---
    # Metadata only (name/key) — deliberately not wrapping /resolve/{key}, which returns the
    # decrypted plaintext secret and shouldn't land in an LLM conversation transcript by default.
    async def list_vault_secrets(self) -> list:
        return _unwrap(await self.get("/rest/api/v2/vault/list"))


managed_testing_client = ManagedTestingClient()
