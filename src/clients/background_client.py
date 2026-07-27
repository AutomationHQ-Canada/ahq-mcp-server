from src.clients.base_client import BaseAhqClient
from src.config.ahq_services import BACKGROUND_SVC


class BackgroundClient(BaseAhqClient):
    """
    Owns: job scheduling, job status polling, queue management.
    Does NOT own execution entry point — use ExecutorClient.execute_bot() for that.
    background-v2-services is called internally by executor-services, not directly by MCP.
    """

    def __init__(self, credentials=None, http_client=None):
        super().__init__(BACKGROUND_SVC, credentials, http_client)

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

    async def cancel_schedule(self, schedule_id: str) -> dict:
        return await self.delete(f"/background-jobs/execution-jobs/schedule-recurring/{schedule_id}")

    # --- Status & Queue ---
    # A job's status describes DISPATCH, not the test outcome: a run whose script failed every
    # assertion still finishes SUCCEEDED here, because the job did what it was asked to do
    # (confirmed live — a bot whose only script FAILED reported SUCCEEDED at this endpoint).
    # Reporting that as the answer to "did my test pass?" states the exact opposite of the truth,
    # so terminal responses carry an explicit pointer to the report that does know.
    _TERMINAL_JOB_STATUSES = {"SUCCEEDED", "FAILED", "DELETED"}

    async def get_job_status(self, job_id: str) -> dict:
        result = await self.get(f"/background-jobs/status/{job_id}/details")
        if isinstance(result, dict) and result.get("status") in self._TERMINAL_JOB_STATUSES:
            result["note"] = (
                f"'{result['status']}' is the JOB's dispatch outcome, NOT the test result — a run "
                "whose assertions all failed still reports SUCCEEDED here. Call list_recent_runs "
                "(for the executionId) then get_execution_report for actual pass/fail."
            )
        return result

    async def get_queue_status(self) -> dict:
        return await self.get("/background-jobs/queue-status")

    # NOTE: there is deliberately no list_recent_runs here — GET /background-jobs/execution-jobs
    # does not exist (ExecutionJobController only has POST run/schedule endpoints). Recent runs
    # come from test-management's TestReportController: see TestMgmtClient.list_recent_reports.
