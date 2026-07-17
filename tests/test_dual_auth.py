import base64
import json

from src.hosted.dual_auth import DualAuthMiddleware
from src.hosted.oauth_provider import AhqTokenVerifier, StatelessAhqProvider
from src.hosted.token_codec import TokenCodec


def _fake_jwt(claims: dict) -> str:
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"eyJhbGciOiJub25lIn0.{payload}.fake-signature"


ORG_TOKEN = _fake_jwt({"organizationId": "org-1", "tokenType": "ORGANIZATION"})
RESOURCE_METADATA_URL = "http://localhost:8000/.well-known/oauth-protected-resource/mcp"


def _middleware(inner_app):
    codec = TokenCodec("test-secret")
    provider = StatelessAhqProvider(codec, "http://localhost:8000")
    mw = DualAuthMiddleware(
        inner_app, AhqTokenVerifier(provider),
        resource_metadata_url=RESOURCE_METADATA_URL,
        base_url="https://api-dev.automationhq.ai",
    )
    return mw, codec


def _scope(headers: list[tuple[bytes, bytes]], method: str = "POST") -> dict:
    return {"type": "http", "method": method, "headers": headers, "path": "/"}


class _Recorder:
    def __init__(self):
        self.messages = []
        self.reached_app = False
        self.seen_scope = None

    async def app(self, scope, receive, send):
        self.reached_app = True
        self.seen_scope = scope
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def send(self, message):
        self.messages.append(message)

    async def receive(self):
        return {"type": "http.request", "body": b"", "more_body": False}


async def test_valid_bearer_stashes_credentials_in_scope():
    rec = _Recorder()
    mw, codec = _middleware(rec.app)
    access = codec.encode("access", {
        "ahq_token": ORG_TOKEN, "org_id": "org-1", "project_id": "proj-1",
        "client_id": "cid", "scopes": [],
    }, 60)

    await mw(_scope([(b"authorization", f"Bearer {access}".encode())]), rec.receive, rec.send)

    assert rec.reached_app
    creds = rec.seen_scope["ahq_credentials"]
    assert creds.api_token == ORG_TOKEN
    assert creds.org_id == "org-1"
    assert creds.project_id == "proj-1"
    assert creds.base_url == "https://api-dev.automationhq.ai"  # never caller-supplied


async def test_valid_bearer_honors_base_url_sealed_in_token():
    # base_url is resolved from the AHQ token's own urlDetails claim at consent time (see
    # oauth_provider._issue_tokens) and sealed into our access-token blob — DualAuthMiddleware
    # must use THAT, not its own fixed server-config base_url, so a prod-token session's tool
    # calls hit prod's gateway even though this server is dev-hosted.
    rec = _Recorder()
    mw, codec = _middleware(rec.app)
    access = codec.encode("access", {
        "ahq_token": ORG_TOKEN, "org_id": "org-1", "project_id": "proj-1",
        "base_url": "https://api.automationhq.ai", "client_id": "cid", "scopes": [],
    }, 60)

    await mw(_scope([(b"authorization", f"Bearer {access}".encode())]), rec.receive, rec.send)

    assert rec.reached_app
    assert rec.seen_scope["ahq_credentials"].base_url == "https://api.automationhq.ai"


async def test_legacy_api_key_header_passes_through():
    rec = _Recorder()
    mw, _ = _middleware(rec.app)
    await mw(_scope([(b"x-api-auth-key", ORG_TOKEN.encode())]), rec.receive, rec.send)
    assert rec.reached_app
    assert "ahq_credentials" not in rec.seen_scope  # _resolve_clients keeps using from_headers


async def test_no_auth_401_with_resource_metadata_in_www_authenticate():
    rec = _Recorder()
    mw, _ = _middleware(rec.app)
    await mw(_scope([]), rec.receive, rec.send)
    assert not rec.reached_app
    start = rec.messages[0]
    assert start["status"] == 401
    headers = dict(start["headers"])
    assert RESOURCE_METADATA_URL.encode() in headers[b"www-authenticate"]


async def test_expired_bearer_401():
    rec = _Recorder()
    mw, codec = _middleware(rec.app)
    expired = codec.encode("access", {
        "ahq_token": ORG_TOKEN, "org_id": "org-1", "project_id": "", "client_id": "c", "scopes": [],
    }, -10)
    await mw(_scope([(b"authorization", f"Bearer {expired}".encode())]), rec.receive, rec.send)
    assert not rec.reached_app
    assert rec.messages[0]["status"] == 401


async def test_options_preflight_passes_through_unauthenticated():
    rec = _Recorder()
    mw, _ = _middleware(rec.app)
    await mw(_scope([], method="OPTIONS"), rec.receive, rec.send)
    assert rec.reached_app
