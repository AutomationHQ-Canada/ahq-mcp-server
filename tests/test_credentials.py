from src.config.credentials import AhqCredentials


def test_from_settings_reads_all_fields():
    class FakeSettings:
        ahq_base_url = "https://api-dev.automationhq.ai"
        ahq_api_token = "tok-123"
        ahq_org_id = "org-1"
        ahq_project_id = "proj-1"

    creds = AhqCredentials.from_settings(FakeSettings())

    assert creds == AhqCredentials(
        base_url="https://api-dev.automationhq.ai", api_token="tok-123", org_id="org-1", project_id="proj-1"
    )


def test_from_headers_reads_ahq_auth_headers():
    headers = {"X-API-AUTH-KEY": "caller-token", "org-id": "caller-org", "projectId": "caller-project"}

    creds = AhqCredentials.from_headers(headers, base_url="https://api-dev.automationhq.ai")

    assert creds.api_token == "caller-token"
    assert creds.org_id == "caller-org"
    assert creds.project_id == "caller-project"


def test_from_headers_base_url_is_never_taken_from_caller():
    # A caller could send an X-Forwarded-Host or similar, but from_headers only accepts
    # base_url as an explicit keyword — there's no header key that can override it.
    headers = {"X-API-AUTH-KEY": "t", "org-id": "o", "projectId": "p", "base_url": "https://evil.example.com"}

    creds = AhqCredentials.from_headers(headers, base_url="https://api-dev.automationhq.ai")

    assert creds.base_url == "https://api-dev.automationhq.ai"


def test_from_headers_missing_headers_default_to_empty_string():
    creds = AhqCredentials.from_headers({}, base_url="https://api-dev.automationhq.ai")

    assert creds.api_token == ""
    assert creds.org_id == ""
    assert creds.project_id == ""
