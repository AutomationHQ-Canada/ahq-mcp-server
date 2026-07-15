import asyncio
import time

import httpx
from src.config.ahq_services import STANDALONE_SVC, settings
from src.config.credentials import decode_ahq_token
from src.clients.base_client import BaseAhqClient


class LocalExecClient(BaseAhqClient):
    """
    Communicates with the local agent (test-local-execution-services) running on
    the user's machine at port 9202. This is NOT routed through the gateway —
    it runs as an Electron desktop agent on localhost.

    Used only when execution type is LOCAL (gridUrlForExecution contains "localhost").
    """

    LOCAL_AGENT_URL = "http://localhost:9202"

    # Class-level, not instance-level: the dispatcher creates a fresh LocalExecClient per tool
    # call, but the agent process it's checking persists across those calls for the life of
    # this MCP server session — so "when did we first see it online" has to live here too.
    _first_online_at: float | None = None

    def __init__(self, credentials=None, http_client=None, now=time.monotonic, sleep=asyncio.sleep,
                 warmup_seconds=None):
        super().__init__(STANDALONE_SVC, credentials, http_client)  # for standalone data access via gateway
        self._local_url = self.LOCAL_AGENT_URL
        self._now = now
        self._sleep = sleep
        # See Settings.ahq_local_agent_warmup_seconds for why this exists: /rest/api/execute/ping
        # is a pure liveness check — it answers within ~8s of the agent's JVM starting, well
        # before the agent has finished its own async startup (org token revalidation,
        # chromedriver/edgedriver resolution). A bot run started in that window can fail to open
        # a browser: the agent's local/remote grid classification depends on a live lookup that
        # can still be warming up, and on misclassification it tries to open a RemoteWebDriver
        # session against a URL nothing is listening on. Waiting out this grace period the first
        # time we see the agent online (not on every call) closes that race without guessing at
        # readiness signals the agent doesn't expose.
        self._warmup_seconds = warmup_seconds if warmup_seconds is not None else settings.ahq_local_agent_warmup_seconds

    async def get_agent_status(self) -> dict:
        """
        Check if the local agent is running on this machine (TestExecutorController's /ping).

        If this is the first time we've observed it online, waits out the configured warm-up
        grace period before returning so callers (execute_bot in particular) don't race the
        agent's own startup. Every call after that returns immediately.
        """
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    f"{self._local_url}/rest/api/execute/ping",
                    timeout=5,
                )
                r.raise_for_status()
                data = r.json()
        except Exception:
            LocalExecClient._first_online_at = None  # next sighting is treated as a fresh start
            return {"online": False, "error": "Local agent not running at localhost:9202"}

        now = self._now()
        if LocalExecClient._first_online_at is None:
            LocalExecClient._first_online_at = now
        elapsed = now - LocalExecClient._first_online_at
        if elapsed < self._warmup_seconds:
            remaining = self._warmup_seconds - elapsed
            await self._sleep(remaining)
            return {
                "online": True,
                "data": data,
                "note": (
                    f"Agent just started — waited {remaining:.0f}s for its browser/session "
                    "subsystems to finish initializing before reporting ready. This avoids a "
                    "known failure where running a bot immediately after the agent starts can "
                    "fail to open a browser."
                ),
            }
        return {"online": True, "data": data}

    @classmethod
    def reset_warmup_tracking(cls):
        """Explicit reset hook (also happens naturally: a failed ping already resets this)."""
        cls._first_online_at = None

    async def execute_bot_locally(self, bot_id: str, execution_configuration: dict, name: str = None) -> dict:
        """
        POST directly to THIS machine's local agent (localhost:9202) — bypasses the cloud
        executor service entirely. Confirmed by capturing a real browser session's HAR: for a
        local-grid execution, the Run TestBot dialog never calls the cloud executor at all — it
        POSTs straight to localhost:9202/rest/api/bots/{botId}/execute from the browser, since
        the browser and the agent are on the same machine. Going through the cloud instead (what
        execute_bot did before this) enqueues a job the cloud has no way to ever deliver to this
        specific developer's own machine — it just sits ENQUEUED forever, which is the actual
        root cause of local executions "hanging" via MCP (a different failure mode than the grid
        misclassification bug, which only matters once a request already reached the agent).

        The /execute call itself doesn't check auth (confirmed via HAR — only same-machine
        processes can reach localhost:9202 in the first place). But the agent's OWN downstream
        calls on this execution's behalf (fetching the TestBot definition, vault secrets, etc.)
        do need a credential: TestBotExecutionController reads X-API-AUTH-KEY off the incoming
        request and stashes it via ProjectContextManager.setApiAuthKey(), and
        BearerTokenInterceptor forwards it on every downstream call. This requires the matching
        fix in test-local-execution-services/ahq-actions-commons (X-API-AUTH-KEY support added
        alongside the pre-existing Authorization/user-session-JWT forwarding — see
        BearerTokenInterceptor's class doc) — an organization token was never valid via
        Authorization there (different signing secret than a user-session JWT entirely; confirmed
        live, twice, that sending it as Authorization still 401s the downstream calls).
        """
        partner_id = decode_ahq_token(self._credentials.api_token).get("partnerId", "")
        headers = {
            "Content-Type": "application/json",
            "X-API-AUTH-KEY": self._credentials.api_token,
            "org-id": self._credentials.org_id,
            "organizationid": self._credentials.org_id,
            "partner-id": partner_id,
            "projectid": self._credentials.project_id,
        }
        body = {"testBotId": bot_id, "executionConfiguration": execution_configuration}
        if name:
            body["name"] = name
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self._local_url}/rest/api/bots/{bot_id}/execute",
                json=body, headers=headers, timeout=30,
            )
            r.raise_for_status()
            return r.json()

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
