from src.clients.base_client import BaseAhqClient
from src.config.ahq_services import EXECUTOR_SVC


class ExecutorClient(BaseAhqClient):
    def __init__(self, credentials=None, http_client=None):
        super().__init__(EXECUTOR_SVC, credentials, http_client)

    async def execute_bot(self, bot_id: str, execution_configuration: dict, partial_execution: bool = False) -> dict:
        """
        Correct entry point for bot execution.
        executor-services validates the bot, fan-outs per browser,
        then internally calls background-v2-services to enqueue the job.
        Returns executionId + jobId.
        """
        return await self.post(
            f"/rest/api/bots/{bot_id}/execute",
            json={"executionConfiguration": execution_configuration},
            timeout=60,
        )

    async def get_bot_execution_status(self, execution_id: str) -> dict:
        return await self.get(f"/rest/api/bots/execution/{execution_id}/status")

    async def get_execution_results(self, execution_id: str) -> dict:
        return await self.get(f"/rest/api/bots/execution/{execution_id}/results")

    async def get_execution_screenshots(self, execution_id: str) -> dict:
        return await self.get(f"/rest/api/screenshots/{execution_id}")

    async def get_performance_report(self, execution_id: str) -> dict:
        return await self.get(f"/rest/api/roi/{execution_id}")
