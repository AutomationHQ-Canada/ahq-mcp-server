import base64
import json

from src.config.credentials import AhqCredentials, decode_ahq_token


def _fake_jwt(**claims) -> str:
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"eyJhbGciOiJub25lIn0.{payload}.fake-signature"


def test_decode_ahq_token_reads_claims():
    token = _fake_jwt(organizationId="org-1", organizationName="Acme")

    claims = decode_ahq_token(token)

    assert claims == {"organizationId": "org-1", "organizationName": "Acme"}


def test_from_settings_derives_org_id_from_token_not_a_separate_setting():
    class FakeSettings:
        ahq_base_url = "https://api-dev.automationhq.ai"
        ahq_api_token = _fake_jwt(organizationId="org-from-token")
        ahq_project_id = "proj-1"

    creds = AhqCredentials.from_settings(FakeSettings())

    assert creds == AhqCredentials(
        base_url="https://api-dev.automationhq.ai",
        api_token=FakeSettings.ahq_api_token,
        org_id="org-from-token",
        project_id="proj-1",
    )


def test_from_headers_derives_org_id_from_token_ignoring_org_id_header():
    # A caller-sent "org-id" header must NOT be trusted for org_id — only the token's own
    # organizationId claim. This is exactly the class of bug that motivated this design: a
    # stale/wrong org-id can silently write real data into the wrong organization since the
    # gateway itself doesn't validate the header against the token's claim.
    token = _fake_jwt(organizationId="org-from-token")
    headers = {"X-API-AUTH-KEY": token, "org-id": "org-that-should-be-ignored", "projectId": "caller-project"}

    creds = AhqCredentials.from_headers(headers, base_url="https://api-dev.automationhq.ai")

    assert creds.api_token == token
    assert creds.org_id == "org-from-token"
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
