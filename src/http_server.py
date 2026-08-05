import contextlib
import os
import secrets as _secrets
import sys
from importlib.metadata import PackageNotFoundError, version as _pkg_version

import httpx
import uvicorn
from pydantic import AnyHttpUrl
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Mount, Route

from mcp.server.auth.handlers.metadata import ProtectedResourceMetadataHandler
from mcp.server.auth.routes import cors_middleware, create_auth_routes
from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.shared.auth import ProtectedResourceMetadata

from src.clients.generic_client import SERVICE_MAP
from src.clients.user_client import UserClient
from src.config.ahq_services import settings as _settings
from src.hosted.body_limit import BodySizeLimitMiddleware
from src.hosted.consent import make_consent_endpoints
from src.hosted.dual_auth import DualAuthMiddleware
from src.hosted.oauth_provider import AhqTokenVerifier, StatelessAhqProvider
from src.hosted.token_codec import TokenCodec
from src.mcp_server import server, app_http_client, TOOLS, _HOSTED_UNSUPPORTED

try:
    _VERSION = _pkg_version("ahq-mcp-server")
except PackageNotFoundError:
    _VERSION = "unknown"


async def healthz(request):
    return PlainTextResponse("ok")


async def status(request):
    return JSONResponse({
        "service": "testbots-mcp-server",
        "version": _VERSION,
        "mode": "hosted",
        "tool_count": len(TOOLS) - len(_HOSTED_UNSUPPORTED),
    })


def _canonical_services():
    # SERVICE_MAP lists each service's canonical long-form name before its short aliases, so
    # keeping the first name seen per prefix (not per key) naturally dedupes aliases while
    # still reflecting a self-hosted deployment's overridden ahq_gw_prefix_* values.
    seen, out = set(), []
    for name, prefix in SERVICE_MAP.items():
        if prefix not in seen:
            seen.add(prefix)
            out.append({"key": name, "prefix": prefix})
    return out


async def tools_catalog(request):
    tools = [
        {"name": t.name, "description": t.description}
        for t in TOOLS if t.name not in _HOSTED_UNSUPPORTED
    ]
    return JSONResponse({"tools": tools, "services": _canonical_services()})


class _ExactMcpPath:
    """
    Starlette's Mount("/mcp") only matches "/mcp/..." and answers a bare "/mcp" with a 307 to
    "/mcp/". Behind the gateway that redirect is a live bug: the Location header is the
    app-local "/mcp/" WITHOUT the /ahq-mcp-server prefix StripPrefix removed, so a client
    following it lands on the gateway root and 404s. Rewrite the exact path instead — clients
    connect to .../mcp and never see a redirect.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path") == "/mcp":
            scope = dict(scope)
            scope["path"] = "/mcp/"
        await self.app(scope, receive, send)


def create_app(settings):
    """
    The hosted (multi-tenant) entrypoint app. Deployed behind the AHQ gateway at
    {AHQ_MCP_PUBLIC_BASE_URL} (e.g. https://api-dev.automationhq.ai/ahq-mcp-server, whose
    /ahq-mcp-server prefix the gateway's StripPrefix=1 removes) — so routes here are
    prefix-less while every URL advertised to OAuth clients (metadata documents, consent
    redirect, WWW-Authenticate resource_metadata) carries the full public prefix. That
    prefixed resource_metadata URL is what makes RFC 9728 discovery round-trip through the
    gateway without any root-level /.well-known route.
    """
    public_base = settings.ahq_mcp_public_base_url.rstrip("/") or "http://localhost:8000"
    # main() refuses to serve without a real secret; the random fallback only exists so tests
    # and one-off local runs can build the app without config (single process — safe there).
    secret = settings.ahq_mcp_auth_secret or _secrets.token_urlsafe(32)

    codec = TokenCodec(secret)
    provider = StatelessAhqProvider(
        codec, public_base, extra_redirect_uris=settings.ahq_mcp_extra_redirect_uris,
    )
    verifier = AhqTokenVerifier(provider)
    resource_metadata_url = f"{public_base}/.well-known/oauth-protected-resource/mcp"

    session_manager = StreamableHTTPSessionManager(app=server, json_response=False, stateless=True)

    @contextlib.asynccontextmanager
    async def lifespan(app):
        app_http_client.client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=200, max_keepalive_connections=50)
        )
        async with session_manager.run():
            yield
        await app_http_client.client.aclose()
        app_http_client.client = None

    consent_get, consent_post = make_consent_endpoints(codec, settings, UserClient, app_http_client)

    # RFC 9728 protected-resource metadata. Registered MANUALLY at the app-local path instead
    # of via the SDK's create_protected_resource_routes: that helper derives the route path
    # from the resource URL's full path (/.well-known/oauth-protected-resource/ahq-mcp-server/mcp),
    # which after the gateway's StripPrefix would never match an incoming request.
    prm_handler = ProtectedResourceMetadataHandler(
        ProtectedResourceMetadata(
            resource=AnyHttpUrl(f"{public_base}/mcp"),
            authorization_servers=[AnyHttpUrl(public_base)],
            resource_name="TestBots MCP Server",
        )
    )

    routes = [
        Route("/healthz", healthz),
        Route("/status", status),
        Route("/tools", tools_catalog),
        Route(
            "/.well-known/oauth-protected-resource/mcp",
            endpoint=cors_middleware(prm_handler.handle, ["GET", "OPTIONS"]),
            methods=["GET", "OPTIONS"],
        ),
        *create_auth_routes(
            provider,
            issuer_url=AnyHttpUrl(public_base),
            client_registration_options=ClientRegistrationOptions(enabled=True),
            revocation_options=RevocationOptions(enabled=False),
        ),
        Route("/consent", consent_get, methods=["GET"]),
        Route("/consent", consent_post, methods=["POST"]),
        Mount(
            "/mcp",
            app=DualAuthMiddleware(
                session_manager.handle_request,
                verifier,
                resource_metadata_url=resource_metadata_url,
                base_url=settings.ahq_base_url,
            ),
        ),
    ]

    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=[
                "Authorization", "Content-Type", "Mcp-Protocol-Version",
                "Mcp-Session-Id", "X-API-AUTH-KEY", "projectId",
            ],
            expose_headers=["Mcp-Session-Id", "WWW-Authenticate"],
        ),
        Middleware(BodySizeLimitMiddleware, max_bytes=settings.ahq_mcp_max_body_bytes),
    ]

    return _ExactMcpPath(Starlette(routes=routes, middleware=middleware, lifespan=lifespan))


app = create_app(_settings)


def main():
    if not _settings.ahq_mcp_auth_secret:
        # No generate-if-missing: replicas would each mint mutually-unreadable tokens, and
        # every restart would silently invalidate all issued tokens. Fail loud instead.
        print(
            "[ahq-mcp-http] FATAL: AHQ_MCP_AUTH_SECRET is not set. Hosted mode requires a "
            "shared secret (same value on every replica) for its stateless OAuth tokens — "
            "set it via the environment / k8s secret ahq-mcp-server-secrets.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    public_base = _settings.ahq_mcp_public_base_url or "http://localhost:8000"
    print(f"[ahq-mcp-http] public_base={public_base} ahq_base_url={_settings.ahq_base_url}",
          file=sys.stderr)
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))


if __name__ == "__main__":
    main()
