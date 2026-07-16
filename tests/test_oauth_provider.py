import base64
import json
import time

import pytest
from pydantic import AnyUrl

from mcp.server.auth.provider import AuthorizationParams, RegistrationError
from mcp.shared.auth import OAuthClientInformationFull

from src.hosted.oauth_provider import (
    ACCESS_TTL,
    AhqTokenVerifier,
    StatelessAhqProvider,
    redirect_uri_allowed,
)
from src.hosted.token_codec import TokenCodec


def _fake_jwt(claims: dict) -> str:
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"eyJhbGciOiJub25lIn0.{payload}.fake-signature"


ORG_TOKEN = _fake_jwt({"organizationId": "org-1", "organizationName": "Org One", "tokenType": "ORGANIZATION"})


def _provider() -> StatelessAhqProvider:
    return StatelessAhqProvider(TokenCodec("test-secret"), "http://localhost:8000")


def _client_info(**overrides) -> OAuthClientInformationFull:
    base = dict(
        client_id="uuid-from-sdk",
        redirect_uris=[AnyUrl("http://localhost:33418/callback")],
        token_endpoint_auth_method="none",
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        client_name="Test Client",
    )
    base.update(overrides)
    return OAuthClientInformationFull.model_validate(base)


def _params(**overrides) -> AuthorizationParams:
    base = dict(
        state="xyz",
        scopes=None,
        code_challenge="challenge",
        redirect_uri=AnyUrl("http://localhost:33418/callback"),
        redirect_uri_provided_explicitly=True,
    )
    base.update(overrides)
    return AuthorizationParams(**base)


async def test_register_client_replaces_uuid_client_id_with_blob():
    # Pins the SDK behavior our stateless registration rides on: RegistrationHandler generates
    # a uuid, calls register_client(client_info), then echoes the SAME mutable model back — so
    # mutating client_id here IS the persistence. If an SDK upgrade stops echoing the mutated
    # model, this design breaks and this test must catch it.
    provider = _provider()
    info = _client_info()
    await provider.register_client(info)
    assert info.client_id != "uuid-from-sdk"
    assert provider.codec.decode("client", info.client_id) is not None


async def test_get_client_round_trips_registration():
    provider = _provider()
    info = _client_info(client_secret="s3cret", token_endpoint_auth_method="client_secret_post")
    await provider.register_client(info)
    loaded = await provider.get_client(info.client_id)
    assert loaded is not None
    assert loaded.client_id == info.client_id
    assert loaded.client_secret == "s3cret"
    assert [str(u) for u in loaded.redirect_uris] == ["http://localhost:33418/callback"]
    assert await provider.get_client("garbage") is None


async def test_get_client_accepts_vscode_style_unregistered_client_id():
    # VS Code's Copilot Chat MCP OAuth client skips DCR entirely (confirmed live 2026-07-16,
    # reproduced in a brand-new temporary profile) and goes straight to /authorize with a
    # self-constructed client_id: its own redirect URIs, space-joined, never registered via
    # /register. Every URI must still independently pass the allowlist.
    provider = _provider()
    client_id = "http://127.0.0.1:33418/ https://vscode.dev/redirect"
    client = await provider.get_client(client_id)
    assert client is not None
    assert client.client_id == client_id
    assert [str(u) for u in client.redirect_uris] == ["http://127.0.0.1:33418/", "https://vscode.dev/redirect"]
    assert client.token_endpoint_auth_method == "none"


async def test_get_client_rejects_unregistered_client_id_with_disallowed_uri():
    provider = _provider()
    assert await provider.get_client("http://127.0.0.1:33418/ https://evil.example.com/cb") is None


async def test_register_rejects_non_loopback_non_claude_redirect():
    provider = _provider()
    info = _client_info(redirect_uris=[AnyUrl("https://evil.example.com/callback")])
    with pytest.raises(RegistrationError) as exc:
        await provider.register_client(info)
    assert exc.value.error == "invalid_redirect_uri"


def test_redirect_policy_allows_loopback_any_port_and_claude_callbacks():
    extra = frozenset()
    assert redirect_uri_allowed("http://localhost:33418/callback", extra)
    assert redirect_uri_allowed("http://127.0.0.1:9999/x", extra)
    assert redirect_uri_allowed("http://[::1]:8080/cb", extra)
    assert redirect_uri_allowed("https://claude.ai/api/mcp/auth_callback", extra)
    assert redirect_uri_allowed("https://claude.com/api/mcp/auth_callback", extra)
    assert redirect_uri_allowed("https://vscode.dev/redirect", extra)
    assert not redirect_uri_allowed("https://localhost:33418/callback", extra)  # https loopback: not RFC 8252
    assert not redirect_uri_allowed("http://192.168.1.5:8000/cb", extra)
    assert redirect_uri_allowed("myapp://oauth/callback", frozenset({"myapp://oauth/callback"}))


async def test_authorize_returns_consent_url_with_txn():
    provider = _provider()
    info = _client_info()
    await provider.register_client(info)
    url = await provider.authorize(info, _params())
    assert url.startswith("http://localhost:8000/consent?txn=")
    from urllib.parse import parse_qs, urlparse

    txn = parse_qs(urlparse(url).query)["txn"][0]
    payload = provider.codec.decode("txn", txn)
    assert payload["client_id"] == info.client_id
    assert payload["client_name"] == "Test Client"
    assert payload["params"]["code_challenge"] == "challenge"


async def test_exchange_code_embeds_ahq_token_and_project():
    provider = _provider()
    code_blob = provider.codec.encode(
        "code",
        {
            "ahq_token": ORG_TOKEN,
            "project_id": "proj-1",
            "client_id": "cid",
            "redirect_uri": "http://localhost:1/cb",
            "redirect_uri_provided_explicitly": True,
            "code_challenge": "challenge",
            "scopes": [],
        },
        300,
    )
    client = _client_info()
    auth_code = await provider.load_authorization_code(client, code_blob)
    assert auth_code is not None
    assert auth_code.ahq_token == ORG_TOKEN
    tokens = await provider.exchange_authorization_code(client, auth_code)

    access = await AhqTokenVerifier(provider).verify_token(tokens.access_token)
    assert access is not None
    assert access.ahq_token == ORG_TOKEN
    assert access.org_id == "org-1"
    assert access.project_id == "proj-1"
    assert tokens.refresh_token is not None


async def test_refresh_rotates_both_tokens():
    provider = _provider()
    client = _client_info()
    first = provider._issue_tokens("cid", ORG_TOKEN, "org-1", "proj-1", [])
    refresh = await provider.load_refresh_token(client, first.refresh_token)
    assert refresh is not None
    second = await provider.exchange_refresh_token(client, refresh, [])
    assert second.access_token != first.access_token
    assert second.refresh_token != first.refresh_token
    access = await provider.load_access_token(second.access_token)
    assert access.ahq_token == ORG_TOKEN
    assert access.project_id == "proj-1"


async def test_access_ttl_capped_by_ahq_token_exp():
    provider = _provider()
    soon = int(time.time()) + 300  # AHQ token dies in 5 minutes — ours must not outlive it
    short_token = _fake_jwt({"organizationId": "org-1", "tokenType": "ORGANIZATION", "exp": soon})
    tokens = provider._issue_tokens("cid", short_token, "org-1", "p", [])
    assert tokens.expires_in <= 300
    assert tokens.expires_in < ACCESS_TTL
    access = await provider.load_access_token(tokens.access_token)
    assert access.expires_at <= soon + 1
