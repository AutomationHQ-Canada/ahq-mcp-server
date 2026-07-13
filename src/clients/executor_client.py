from src.clients.base_client import BaseAhqClient
from src.config.ahq_services import EXECUTOR_SVC


class ExecutorClient(BaseAhqClient):
    def __init__(self, credentials=None, http_client=None):
        super().__init__(EXECUTOR_SVC, credentials, http_client)

    async def execute_bot(self, bot_id: str, execution_configuration: dict,
                          name: str = None, profile_id: str = None,
                          partial_execution: bool = False) -> dict:
        """
        POST /rest/api/bots/{botId}/execute (TestBotExecutionController) — the cloud execution
        entry point. Body is a BotExecution: the server forces org/project/testBotId/timestamps/
        createdBy itself and validates the bot's suites + scripts + grid access before enqueuing.
        The frontend's run dialog also sends name (execution display name) and profileId
        top-level, alongside executionConfiguration.
        """
        body = {"executionConfiguration": execution_configuration}
        if name:
            body["name"] = name
        if profile_id:
            body["profileId"] = profile_id
        return await self.post(
            f"/rest/api/bots/{bot_id}/execute",
            json=body,
            params={"partialExecution": "true"} if partial_execution else None,
            timeout=60,
        )

    async def get_bot_execution_status(self, execution_id: str) -> dict:
        return await self.get(f"/rest/api/bots/execution/{execution_id}/status")

    async def get_execution_results(self, execution_id: str) -> dict:
        # Real endpoint is /detailed-results (GetMapping in TestBotExecutionController).
        # The previously-used /execution/{id}/results path does not exist anywhere.
        return await self.get(f"/rest/api/bots/execution/{execution_id}/detailed-results")

    async def get_execution_screenshots(self, execution_id: str) -> dict:
        return await self.get(f"/rest/api/screenshots/{execution_id}")

    async def get_performance_report(self, execution_id: str) -> dict:
        return await self.get(f"/rest/api/roi/{execution_id}")
