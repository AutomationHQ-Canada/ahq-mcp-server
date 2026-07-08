from src.clients.base_client import BaseAhqClient
from src.config.ahq_services import EMAIL_SVC


class EmailClient(BaseAhqClient):
    def __init__(self):
        super().__init__(EMAIL_SVC)

    async def send_email(
        self,
        to: str,
        subject: str,
        message: str,
        multiple_tos: list = None,
        from_address: str = None,
    ) -> str:
        payload = {"to": to, "subject": subject, "message": message}
        if multiple_tos:
            payload["multipleTos"] = multiple_tos
        if from_address:
            payload["from"] = from_address
        # Controller returns a bare job-id string; r.json() parses it fine as a JSON string literal.
        return await self.post("/background-jobs/email-jobs/run-job", json=payload)


email_client = EmailClient()
