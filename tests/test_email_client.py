import httpx

from src.clients.email_client import EmailClient


def _client_with_fake_transport(fake_request):
    client = EmailClient()
    client._client.request = fake_request
    return client


async def test_send_email_posts_to_run_job_and_returns_job_id():
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["json"] = kwargs["json"]
        return httpx.Response(200, json="job-abc-123", request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.send_email("qa@example.com", "Test run complete", "All green.")

    assert captured["method"] == "POST"
    assert captured["url"] == "https://api-dev.automationhq.ai/ahq-email-v2-services/background-jobs/email-jobs/run-job"
    assert captured["json"] == {"to": "qa@example.com", "subject": "Test run complete", "message": "All green."}
    assert result == "job-abc-123"
