import httpx
from src.config.ahq_services import settings, STANDALONE_SVC
from src.clients.base_client import BaseAhqClient


class LocalExecClient(BaseAhqClient):
    """
    Communicates with the local agent (test-local-execution-services) running on
    the user's machine at port 9202. This is NOT routed through the gateway —
    it runs as an Electron desktop agent on localhost.

    Used only when execution type is LOCAL (gridUrlForExecution contains "localhost").
    """

    LOCAL_AGENT_URL = "http://localhost:9202"

    def __init__(self):
        super().__init__(STANDALONE_SVC)  # for standalone data access via gateway
        self._local_url = self.LOCAL_AGENT_URL

    async def get_agent_status(self) -> dict:
        """Check if local agent is running on this machine."""
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    f"{self._local_url}/rest/api/agent/status",
                    timeout=5,
                )
                r.raise_for_status()
                return {"online": True, "data": r.json()}
        except Exception:
            return {"online": False, "error": "Local agent not running at localhost:9202"}

    async def list_registered_agents(self) -> list:
        """List all registered local agents in the project (via standalone service through gateway)."""
        result = await self.get("/resources/local-agent/get-all")
        return result if isinstance(result, list) else result.get("content", result)

    async def get_test_bot_definition(self, bot_id: str) -> dict:
        """Fetch bot definition via standalone service (used by local execution pipeline)."""
        return await self.get(f"/executor/rest/api/getTestBots/{bot_id}")

    async def list_environments(self) -> list:
        """Fetch execution environments via standalone service."""
        result = await self.get("/executor/rest/api/environments")
        return result if isinstance(result, list) else result.get("content", result)


local_exec_client = LocalExecClient()
