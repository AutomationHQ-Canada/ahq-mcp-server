"""
Full OAuth flow end-to-end against the real Starlette app (register -> authorize -> consent ->
token -> authenticated /mcp initialize), with only the AHQ gateway call (UserClient.list_projects)
monkeypatched. starlette.testclient.TestClient runs the lifespan, so the session manager and
shared httpx client are live.
"""

import base64
import hashlib
import json
import time
import types
from urllib.parse import parse_qs, urlparse

import pytest
from starlette.testclient import TestClient

from src.clients.user_client import UserClient
from src.http_server import create_app


def _fake_jwt(claims: dict) -> str:
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"eyJhbGciOiJub25lIn0.{payload}.fake-signature"


ORG_TOKEN = _fake_jwt({"organizationId": "org-1", "organizationName": "Org One", "tokenType": "ORGANIZATION"})
# Claim set matches a real USER token (TokenService.createClaims, verified against a live one
# 2026-07-28): userId/email/name and organizationId, but NO organizationName — that claim only
# exists on ORGANIZATION tokens, which is why the banner needs a fallback.
USER_TOKEN = _fake_jwt({
    "organizationId": "org-1", "tokenType": "USER",
    "userId": "user-1", "email": "om@example.com", "name": "om raut",
})
# Neither of the two types AHQ mints — the flow must still refuse this.
UNKNOWN_TYPE_TOKEN = _fake_jwt({"organizationId": "org-1", "tokenType": "SERVICE"})
NO_TYPE_TOKEN = _fake_jwt({"organizationId": "org-1"})
# A real prod token embeds urlDetails.baseUrl = https://api.automationhq.ai (confirmed live
# 2026-07-17) — this dev-hosted server must resolve THAT gateway for this token, not its own
# fixed AHQ_BASE_URL (dev).
PROD_ORG_TOKEN = _fake_jwt({
    "organizationId": "org-prod", "organizationName": "Org Prod", "tokenType": "ORGANIZATION",
    "urlDetails": [{"key": "baseUrl", "value": "https://api.automationhq.ai"}],
})

VERIFIER = "a" * 43
CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).decode().rstrip("=")
REDIRECT_URI = "http://localhost:33418/callback"


def _cfg(**overrides):
    base = dict(
        ahq_base_url="https://api-dev.automationhq.ai",
        ahq_mcp_public_base_url="",  # -> http://localhost:8000
        ahq_mcp_auth_secret="test-secret",
        ahq_mcp_extra_redirect_uris="",
        ahq_mcp_max_body_bytes=2_000_000,
    )
    base.update(overrides)
    return types.SimpleNamespace(**base)


@pytest.fixture
def client(monkeypatch):
    seen_base_urls = []

    async def fake_list_projects(self):
        seen_base_urls.append(self._credentials.base_url)
        if self._credentials.api_token not in (
            ORG_TOKEN, PROD_ORG_TOKEN, USER_TOKEN, SHORT_LIVED_ORG_TOKEN,
        ):
            raise RuntimeError("401 from gateway")
        # Real /projects/organizations/{orgId}/all shape: `_id` + `projectName`
        # (confirmed live 2026-07-14 — NOT projectId/name).
        return [{"_id": "proj-1", "projectName": "Project One"},
                {"_id": "proj-2", "projectName": "Project Two"}]

    monkeypatch.setattr(UserClient, "list_projects", fake_list_projects)
    with TestClient(create_app(_cfg()), follow_redirects=False) as c:
        c.seen_base_urls = seen_base_urls
        yield c


def _register(client) -> dict:
    resp = client.post("/register", json={
        "redirect_uris": [REDIRECT_URI],
        "token_endpoint_auth_method": "none",
        "client_name": "Flow Test",
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


def _authorize_to_txn(client, client_id: str) -> str:
    resp = client.get("/authorize", params={
        "client_id": client_id,
        "response_type": "code",
        "code_challenge": CHALLENGE,
        "code_challenge_method": "S256",
        "redirect_uri": REDIRECT_URI,
        "state": "state-xyz",
    })
    assert resp.status_code == 302, resp.text
    location = resp.headers["location"]
    assert location.startswith("http://localhost:8000/consent?txn=")
    return parse_qs(urlparse(location).query)["txn"][0]


def _consent_to_code(client, txn: str, token: str = ORG_TOKEN, project_id: str = "proj-1"):
    return client.post("/consent", data={"txn": txn, "ahq_token": token, "project_id": project_id})


def test_full_flow_register_authorize_consent_token_mcp_initialize(client):
    reg = _register(client)
    txn = _authorize_to_txn(client, reg["client_id"])

    consent = _consent_to_code(client, txn)
    assert consent.status_code == 302, consent.text
    redirect = urlparse(consent.headers["location"])
    assert redirect.netloc == "localhost:33418"
    query = parse_qs(redirect.query)
    assert query["state"] == ["state-xyz"]
    code = query["code"][0]

    token_resp = client.post("/token", data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": reg["client_id"],
        "code_verifier": VERIFIER,
    })
    assert token_resp.status_code == 200, token_resp.text
    tokens = token_resp.json()
    assert tokens["token_type"] == "Bearer"
    assert tokens["refresh_token"]

    mcp_resp = client.post(
        "/mcp",
        headers={
            "Authorization": f"Bearer {tokens['access_token']}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                       "clientInfo": {"name": "flow-test", "version": "0"}},
        },
    )
    assert mcp_resp.status_code == 200, mcp_resp.text

    # Refresh rotates both tokens
    refresh_resp = client.post("/token", data={
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
        "client_id": reg["client_id"],
    })
    assert refresh_resp.status_code == 200, refresh_resp.text
    assert refresh_resp.json()["access_token"] != tokens["access_token"]


def test_pkce_wrong_verifier_rejected(client):
    reg = _register(client)
    txn = _authorize_to_txn(client, reg["client_id"])
    code = parse_qs(urlparse(_consent_to_code(client, txn).headers["location"]).query)["code"][0]

    resp = client.post("/token", data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": reg["client_id"],
        "code_verifier": "b" * 43,
    })
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_grant"


def test_consent_accepts_a_user_token(client):
    """A personal API token must complete the flow, not just be recognised.

    Both AHQ token types carry organizationId and urlDetails, which is everything consent needs;
    the type check was the only thing rejecting USER tokens (confirmed against a live one).
    """
    reg = _register(client)
    txn = _authorize_to_txn(client, reg["client_id"])
    resp = _consent_to_code(client, txn, token=USER_TOKEN)
    assert resp.status_code == 302, resp.text
    assert "code=" in resp.headers["location"]


def test_user_token_banner_names_the_person_not_a_raw_org_id(client):
    """USER tokens carry no organizationName, so the naive fallback prints a bare UUID.

    Reaching the picker requires omitting project_id, which is also the path a real user takes
    when their org has more than one project.
    """
    reg = _register(client)
    txn = _authorize_to_txn(client, reg["client_id"])
    resp = client.post("/consent", data={"txn": txn, "ahq_token": USER_TOKEN, "project_id": ""})
    assert resp.status_code == 200
    assert "om raut (om@example.com)" in resp.text
    assert "organization org-1" not in resp.text


def test_consent_still_rejects_a_token_of_neither_type(client):
    for token in (UNKNOWN_TYPE_TOKEN, NO_TYPE_TOKEN):
        reg = _register(client)
        txn = _authorize_to_txn(client, reg["client_id"])
        resp = _consent_to_code(client, txn, token=token)
        assert resp.status_code == 400, resp.text
        assert "API token" in resp.text


def test_consent_rejects_gateway_invalid_token(client):
    reg = _register(client)
    txn = _authorize_to_txn(client, reg["client_id"])
    bogus = _fake_jwt({"organizationId": "org-x", "tokenType": "ORGANIZATION"})
    resp = _consent_to_code(client, txn, token=bogus)
    assert resp.status_code == 400
    assert "rejected" in resp.text


def test_consent_rejects_project_not_in_org(client):
    # Slice 9k at consent time: a project id from a different org can't be sealed into a token.
    reg = _register(client)
    txn = _authorize_to_txn(client, reg["client_id"])
    resp = _consent_to_code(client, txn, project_id="someone-elses-project")
    assert resp.status_code == 400
    assert "does not belong" in resp.text
    assert "Project One" in resp.text  # picker offered as the fix


def test_consent_without_project_renders_picker(client):
    reg = _register(client)
    txn = _authorize_to_txn(client, reg["client_id"])
    resp = _consent_to_code(client, txn, project_id="")
    assert resp.status_code == 200
    assert 'type="radio"' in resp.text
    assert "Project Two" in resp.text
    assert "Org One" in resp.text  # org-name confirmation banner
    assert "(proj-2)" not in resp.text  # id must not be shown alongside the name, only in value=


def test_consent_first_screen_has_no_project_id_field(client):
    reg = _register(client)
    txn = _authorize_to_txn(client, reg["client_id"])
    resp = client.get("/consent", params={"txn": txn})
    assert resp.status_code == 200
    assert 'name="project_id"' not in resp.text
    assert 'name="ahq_token"' in resp.text


def test_consent_page_uses_default_ahq_branding_when_unconfigured(client):
    reg = _register(client)
    txn = _authorize_to_txn(client, reg["client_id"])
    resp = client.get("/consent", params={"txn": txn})
    assert "AutomationHQ" in resp.text
    assert "#9c27b0" in resp.text
    assert "CA UTAP" not in resp.text


def test_consent_page_uses_partner_branding_when_configured(monkeypatch):
    async def fake_list_projects(self):
        return [{"_id": "proj-1", "projectName": "Project One"}]

    monkeypatch.setattr(UserClient, "list_projects", fake_list_projects)
    cfg = _cfg(
        ahq_mcp_partner_display_name="CA UTAP",
        ahq_mcp_partner_logo_url="https://example.com/ca-utap-logo.svg",
        ahq_mcp_partner_primary_color="#123456",
    )
    with TestClient(create_app(cfg), follow_redirects=False) as c:
        reg = _register(c)
        txn = _authorize_to_txn(c, reg["client_id"])
        resp = c.get("/consent", params={"txn": txn})

        assert resp.status_code == 200
        assert "CA UTAP" in resp.text
        assert "AutomationHQ" not in resp.text
        assert "https://example.com/ca-utap-logo.svg" in resp.text
        assert "#123456" in resp.text
        assert "#9c27b0" not in resp.text

        # Rejection message also uses the partner name, not a hardcoded "AutomationHQ".
        rejected = _consent_to_code(c, txn, token=UNKNOWN_TYPE_TOKEN)
        assert "CA UTAP API token" in rejected.text


def test_consent_resolves_prod_gateway_from_token(client):
    # This server is dev-hosted (ahq_base_url=https://api-dev...), but a prod org token's own
    # urlDetails must make list_projects hit prod's gateway instead — the same consent URL
    # correctly serving both environments.
    reg = _register(client)
    txn = _authorize_to_txn(client, reg["client_id"])
    resp = _consent_to_code(client, txn, token=PROD_ORG_TOKEN, project_id="proj-1")
    assert resp.status_code == 302, resp.text
    assert client.seen_base_urls[-1] == "https://api.automationhq.ai"


def test_prod_token_session_survives_into_mcp_credentials(client):
    # The base_url resolved at consent time (prod) must still be the one used for every
    # subsequent /mcp tool call's credentials, not this server's own dev AHQ_BASE_URL. Unit
    # coverage for the base_url propagation itself lives in test_dual_auth.py and
    # test_oauth_provider.py; this confirms the prod-sourced token round-trips through the full
    # register->authorize->consent->token->/mcp pipeline without breaking.
    reg = _register(client)
    txn = _authorize_to_txn(client, reg["client_id"])
    consent = _consent_to_code(client, txn, token=PROD_ORG_TOKEN, project_id="proj-1")
    assert consent.status_code == 302, consent.text
    code = parse_qs(urlparse(consent.headers["location"]).query)["code"][0]

    token_resp = client.post("/token", data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": reg["client_id"],
        "code_verifier": VERIFIER,
    })
    assert token_resp.status_code == 200, token_resp.text
    access_token = token_resp.json()["access_token"]

    mcp_resp = client.post(
        "/mcp",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                       "clientInfo": {"name": "flow-test", "version": "0"}},
        },
    )
    assert mcp_resp.status_code == 200


def test_expired_txn_shows_expired_page(client):
    resp = client.get("/consent", params={"txn": "garbage"})
    assert resp.status_code == 400
    assert "expired" in resp.text.lower()


def test_metadata_documents_served(client):
    asm = client.get("/.well-known/oauth-authorization-server")
    assert asm.status_code == 200
    meta = asm.json()
    assert meta["issuer"].rstrip("/") == "http://localhost:8000"
    assert meta["code_challenge_methods_supported"] == ["S256"]
    assert "registration_endpoint" in meta

    prm = client.get("/.well-known/oauth-protected-resource/mcp")
    assert prm.status_code == 200
    prm_meta = prm.json()
    assert prm_meta["resource"].rstrip("/").endswith("/mcp")
    assert prm_meta["authorization_servers"]


def test_unauthenticated_mcp_401_with_resource_metadata(client):
    resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert resp.status_code == 401
    www = resp.headers["www-authenticate"]
    assert "resource_metadata=" in www
    assert "/.well-known/oauth-protected-resource/mcp" in www


def test_oversized_body_rejected_413():
    with TestClient(create_app(_cfg(ahq_mcp_max_body_bytes=100)), follow_redirects=False) as c:
        resp = c.post("/mcp", content=b"x" * 500, headers={"Content-Type": "application/json"})
        assert resp.status_code == 413


# --- third field report: two ways a valid token still dead-ends -----------------------------

EMPTY_ORG_TOKEN = _fake_jwt({
    "organizationId": "org-empty", "organizationName": "Empty Org", "tokenType": "ORGANIZATION",
})
# expiryMinutes=480 is an option the platform's own token dialog offers, and 29% of live
# ORGANIZATION tokens use it. _capped_ttl binds BOTH our access and refresh tokens to this, so the
# whole connection dies with it — the reported "I have to re-enter the token constantly".
SHORT_LIVED_ORG_TOKEN = _fake_jwt({
    "organizationId": "org-1", "organizationName": "Org One", "tokenType": "ORGANIZATION",
    "exp": int(time.time()) + 8 * 3600,
})


@pytest.fixture
def client_with_empty_org(monkeypatch):
    async def fake_list_projects(self):
        if self._credentials.api_token == EMPTY_ORG_TOKEN:
            return []
        return [{"_id": "proj-1", "projectName": "Project One"}]

    monkeypatch.setattr(UserClient, "list_projects", fake_list_projects)
    with TestClient(create_app(_cfg()), follow_redirects=False) as c:
        yield c


def test_a_valid_token_whose_org_has_no_projects_says_so(client_with_empty_org):
    """Otherwise: a 'Choose a project' form with no options and a required radio.

    The user cannot submit it and is told nothing, so it reads as "my token is rejected" while a
    colleague's token on a populated org works — indistinguishable from an auth bug. An
    organization holding a valid ORGANIZATION token and zero projects exists in live dev data.
    """
    reg = _register(client_with_empty_org)
    txn = _authorize_to_txn(client_with_empty_org, reg["client_id"])
    resp = client_with_empty_org.post(
        "/consent", data={"txn": txn, "ahq_token": EMPTY_ORG_TOKEN, "project_id": ""},
    )
    assert resp.status_code == 400
    assert "no projects yet" in resp.text
    assert 'type="radio"' not in resp.text, "must not offer an empty, unsubmittable picker"


def test_a_short_lived_token_warns_before_it_becomes_a_support_ticket(client):
    """We cannot outlive the credential we wrap — so say so while the user can still act on it."""
    reg = _register(client)
    txn = _authorize_to_txn(client, reg["client_id"])
    resp = client.post(
        "/consent", data={"txn": txn, "ahq_token": SHORT_LIVED_ORG_TOKEN, "project_id": ""},
    )
    assert resp.status_code == 200
    assert "expires in about 8 hours" in resp.text
    assert "longer-lived token" in resp.text


def test_a_normal_year_long_token_is_not_nagged(client):
    reg = _register(client)
    txn = _authorize_to_txn(client, reg["client_id"])
    resp = client.post("/consent", data={"txn": txn, "ahq_token": ORG_TOKEN, "project_id": ""})
    assert resp.status_code == 200
    assert "expires in about" not in resp.text
