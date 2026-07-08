import httpx
from src.config.ahq_services import STANDALONE_SVC
from src.clients.base_client import BaseAhqClient


class LocalExecClient(BaseAhqClient):
    """
    Communicates with the local agent (test-local-execution-services) running on
    the user's machine at port 9202. This is NOT routed through the gateway —
    it runs as an Electron desktop agent on localhost.

    Used only when execution type is LOCAL (gridUrlForExecution contains "localhost").
    """

    LOCAL_AGENT_URL = "http://localhost:9202"

    def __init__(self, credentials=None, http_client=None):
        super().__init__(STANDALONE_SVC, credentials, http_client)  # for standalone data access via gateway
        self._local_url = self.LOCAL_AGENT_URL

    async def get_agent_status(self) -> dict:
        """Check if the local agent is running on this machine (TestExecutorController's /ping)."""
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    f"{self._local_url}/rest/api/execute/ping",
                    timeout=5,
                )
                r.raise_for_status()
                return {"online": True, "data": r.json()}
        except Exception:
            return {"online": False, "error": "Local agent not running at localhost:9202"}

    async def list_registered_agents(self) -> list:
        """List all registered local agents in the project (via standalone-local-v2 service through gateway)."""
        result = await self.get("/rest/api/local/agent/getAllAgents", extra_headers={"orgId": self._credentials.org_id})
        return result if isinstance(result, list) else result.get("content", result)

    async def get_test_bot_definition(self, bot_id: str) -> dict:
        """Fetch bot definition via standalone service (used by local execution pipeline)."""
        return await self.get(f"/executor/rest/api/getTestBots/{bot_id}")

    async def list_environments(self) -> list:
        """Fetch execution environments via standalone service."""
        result = await self.get("/executor/rest/api/environments")
        return result if isinstance(result, list) else result.get("content", result)

    # --- Fake Data (colocated here since it's the same underlying STANDALONE_SVC, not because
    # it's related to local execution) ---
    async def list_fake_data_types(self) -> list:
        """Display names of available fake-data generators (e.g. 'Email', 'SIN', 'Full Name')."""
        return await self.get("/rest/api/fake-data/display-name")

    async def generate_fake_data(self, display_name: str) -> str:
        return await self.post("/rest/api/fake-data/generate", json={"displayName": display_name})
