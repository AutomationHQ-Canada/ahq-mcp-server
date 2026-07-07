from src.clients.base_client import BaseAhqClient
from src.config.ahq_services import BACKGROUND_SVC


class BackgroundClient(BaseAhqClient):
    """
    Owns: job scheduling, job status polling, queue management.
    Does NOT own execution entry point — use ExecutorClient.execute_bot() for that.
    background-v2-services is called internally by executor-services, not directly by MCP.
    """

    def __init__(self):
        super().__init__(BACKGROUND_SVC)

    # --- Scheduling ---
    async def schedule_bot_recurring(self, bot_id: str, execution_configuration: dict, cron: str) -> dict:
        return await self.post(
            "/background-jobs/execution-jobs/schedule-recurring",
            json={
                "botId": bot_id,
                "execution": {"executionConfiguration": execution_configuration},
                "cronExpression": cron,
                "recurring": True,
            },
        )

    async def schedule_bot_once(self, bot_id: str, execution_configuration: dict, epoch_ms: int) -> dict:
        return await self.post(
            "/background-jobs/execution-jobs/schedule-once-at",
            json={
                "botId": bot_id,
                "execution": {"executionConfiguration": execution_configuration},
                "scheduledAtEpochMs": epoch_ms,
            },
        )

    async def cancel_schedule(self, schedule_id: str) -> dict:
        return await self.delete(f"/background-jobs/execution-jobs/schedule-recurring/{schedule_id}")

    # --- Status & Queue ---
    async def get_job_status(self, job_id: str) -> dict:
        return await self.get(f"/background-jobs/status/{job_id}/details")

    async def get_queue_status(self) -> dict:
        return await self.get("/background-jobs/queue-status")

    async def list_recent_runs(self, bot_id: str = None, limit: int = 10) -> list:
        params = {"size": limit}
        if bot_id:
            params["botId"] = bot_id
        result = await self.get("/background-jobs/execution-jobs", params=params)
        return result.get("content", result) if isinstance(result, dict) else result


background_client = BackgroundClient()
