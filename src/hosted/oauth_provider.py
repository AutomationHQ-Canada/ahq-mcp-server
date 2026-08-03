import time
from urllib.parse import urlencode, urlparse

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    RegistrationError,
    TokenError,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from src.config.credentials import decode_ahq_token
from src.hosted.token_codec import TokenCodec

# Blob lifetimes. Everything is self-contained (no storage), so "revoking" a client or token
# isn't possible — the backstop is that every downstream AHQ call carries the embedded AHQ API
# token, which the gateway re-validates against Mongo's `tokens` collection on every request;
# a deleted/revoked AHQ token dies at the caller's next tool call regardless of these TTLs.
# A client_id blob outlives the others on purpose: clients that persist their registration in a
# deployed artifact (Microsoft 365 Agents Toolkit writes it into the declarative agent's plugin
# manifest) keep presenting the same one indefinitely, so a short life expires the deployment
# itself rather than any credential. The blob carries only redirect URIs and client metadata —
# no AHQ token, which lives in the access token — and each of those URIs already passed
# redirect_uri_allowed, so its lifetime isn't what bounds access. One year matches the AHQ
# organization API token's own expiry window.
CLIENT_TTL = 365 * 24 * 3600
TXN_TTL = 10 * 60
CODE_TTL = 5 * 60
ACCESS_TTL = 8 * 3600
REFRESH_TTL = 30 * 24 * 3600

# Non-loopback redirect URIs that are always acceptable: known first-party client web callbacks.
# VS Code (github.copilot-chat's generic MCP OAuth client) uses vscode.dev/redirect even for a
# local desktop session — confirmed live 2026-07-16: registration 400'd on this exact URI, VS
# Code fell back to a synthesized (invalid) client_id instead of surfacing the registration
# error, and /authorize then failed with "Client ID ... not found" — a confusing second-hand
# symptom of the real, first failure at /register.
KNOWN_CLIENT_CALLBACKS = (
    "https://claude.ai/api/mcp/auth_callback",
    "https://claude.com/api/mcp/auth_callback",
    "https://vscode.dev/redirect",
    # Microsoft 365 Copilot declarative agents: Copilot acquires the user's token through the
    # Teams platform, which uses this one fixed callback for every agent and tenant (unlike
    # Copilot Studio's per-connector Power Platform URI below).
    "https://teams.microsoft.com/api/platform/v1.0/oAuthRedirect",
    # Lovable custom MCP "chat connectors": one fixed first-party callback for every workspace
    # and connection, so a literal entry works where Copilot Studio needed a host rule.
    "https://api.lovable.dev/workspaces/connectors/mcp/oauth/callback",
)

# Microsoft Copilot Studio reaches MCP servers through Power Platform's connector
# infrastructure, whose OAuth callback is per-connector and per-region:
# https://<region>.consent.azure-apim.net/redirect/<connector-id> (global, europe, asia, ...).
# The connector id doesn't exist until after the connector is created, so an exact-match entry
# in AHQ_MCP_EXTRA_REDIRECT_URIS can't be configured ahead of the Dynamic Client Registration
# that Copilot Studio's "Dynamic discovery" option performs — hence a host rule rather than a
# literal. azure-apim.net is Microsoft-owned, so this is the same trust posture as the
# vscode.dev entry above, not an open wildcard.
_POWER_PLATFORM_CONSENT_HOST = "consent.azure-apim.net"


def _is_power_platform_consent_uri(parsed) -> bool:
    host = parsed.hostname or ""
    return (
        parsed.scheme == "https"
        and (host == _POWER_PLATFORM_CONSENT_HOST or host.endswith("." + _POWER_PLATFORM_CONSENT_HOST))
        and (parsed.path == "/redirect" or parsed.path.startswith("/redirect/"))
    )


def redirect_uri_allowed(uri: str, extra: frozenset[str]) -> bool:
    """
    Registration-time redirect-URI policy: loopback http (any port, any path — RFC 8252 native
    clients like Claude Code, Cursor and MCP Inspector listen on a random localhost port), known
    first-party client web callbacks (Claude web/desktop, VS Code), a Power Platform connector
    consent callback (Copilot Studio — see above), or an operator-configured extra
    (AHQ_MCP_EXTRA_REDIRECT_URIS). Everything else is refused — a permissive policy here would
    let any website register itself and receive authorization codes.
    """
    if uri in KNOWN_CLIENT_CALLBACKS or uri in extra:
        return True
    parsed = urlparse(uri)
    if _is_power_platform_consent_uri(parsed):
        return True
    return parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")


class AhqAuthorizationCode(AuthorizationCode):
    ahq_token: str
    project_id: str = ""
    base_url: str = ""
    # Resolved at consent time rather than re-derived here. An API token names its own
    # organization in its claims; the JWT that password sign-in issues does not (it carries only
    # sub/authorities/tier), so the org has to travel with the code instead.
    org_id: str = ""


class AhqRefreshToken(RefreshToken):
    ahq_token: str
    org_id: str = ""
    project_id: str = ""
    base_url: str = ""


class AhqAccessToken(AccessToken):
    ahq_token: str = ""
    org_id: str = ""
    project_id: str = ""
    base_url: str = ""


def _capped_ttl(ahq_token: str, base_ttl: int) -> int:
    """Never issue our token past the embedded AHQ token's own expiry."""
    exp = decode_ahq_token(ahq_token).get("exp")
    if isinstance(exp, (int, float)):
        remaining = int(exp - time.time())
        if remaining < base_ttl:
            return max(60, remaining)
    return base_ttl


class StatelessAhqProvider(OAuthAuthorizationServerProvider):
    """
    OAuth 2.1 authorization server with zero storage: the client_id, authorization code and
    access/refresh tokens are all TokenCodec blobs, so any pod can serve any step of a flow
    another pod started. AHQ has no authorization server of its own (verified 2026-07-14 —
    the platform validates API tokens by a Mongo existence lookup), so this provider IS the
    authorization server; the "login" is the /consent page where the user pastes their AHQ
    ORGANIZATION API token, which gets validated live and sealed into the issued tokens.
    """

    def __init__(self, codec: TokenCodec, public_base_url: str, extra_redirect_uris: str = ""):
        self.codec = codec
        self.public_base_url = public_base_url.rstrip("/")
        self.extra_redirect_uris = frozenset(
            u.strip() for u in extra_redirect_uris.split(",") if u.strip()
        )

    # --- Dynamic client registration (RFC 7591), storage-free ---

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        for uri in client_info.redirect_uris or []:
            if not redirect_uri_allowed(str(uri), self.extra_redirect_uris):
                raise RegistrationError(
                    error="invalid_redirect_uri",
                    error_description=(
                        f"redirect_uri '{uri}' is not allowed: must be a loopback http URI, "
                        f"a Claude callback, or configured in AHQ_MCP_EXTRA_REDIRECT_URIS"
                    ),
                )
        # The SDK's RegistrationHandler generates a uuid client_id, calls this method, then
        # echoes the SAME mutable model back to the client — so replacing client_id here with a
        # self-contained encrypted copy of the whole registration record IS the persistence.
        # (Load-bearing SDK behavior, pinned by test_register_client_replaces_uuid_client_id.)
        record = client_info.model_dump(mode="json", exclude={"client_id"}, exclude_none=True)
        client_info.client_id = self.codec.encode("client", {"reg": record}, CLIENT_TTL)

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        payload = self.codec.decode("client", client_id)
        if payload is not None:
            return OAuthClientInformationFull.model_validate({**payload["reg"], "client_id": client_id})
        return self._implicit_client(client_id)

    def _implicit_client(self, client_id: str) -> OAuthClientInformationFull | None:
        """
        VS Code's Copilot Chat MCP OAuth client skips Dynamic Client Registration (RFC 7591)
        entirely — confirmed live 2026-07-16, reproduced in a brand-new temporary profile with
        zero cached state, so it's the client's actual behavior, not a caching artifact. It goes
        straight to /authorize with a self-constructed, never-registered client_id: its own
        redirect URIs, space-joined (e.g. "http://127.0.0.1:33418/ https://vscode.dev/redirect").
        Since every real client here is already reduced to "does each redirect_uri pass the
        allowlist" (register_client above does nothing else with them), there's no meaningful
        security distinction between "registered via /register" and "self-declared, every URI
        independently allowed" — so treat the latter as an implicit public client rather than
        hard-failing a client that never violates the actual boundary (the allowlist). The SDK's
        authorize handler still independently validates the requested redirect_uri is exactly one
        of these declared ones (client.validate_redirect_uri), so this doesn't loosen that check.
        """
        uris = client_id.split()
        if not uris or not all(redirect_uri_allowed(u, self.extra_redirect_uris) for u in uris):
            return None
        return OAuthClientInformationFull(
            client_id=client_id,
            redirect_uris=uris,
            token_endpoint_auth_method="none",
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
        )

    # --- Authorization: hand off to the /consent page ---

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        txn = self.codec.encode(
            "txn",
            {
                "client_id": client.client_id,
                "client_name": client.client_name or "an MCP client",
                "params": params.model_dump(mode="json"),
            },
            TXN_TTL,
        )
        return f"{self.public_base_url}/consent?{urlencode({'txn': txn})}"

    # --- Code exchange ---

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AhqAuthorizationCode | None:
        payload = self.codec.decode("code", authorization_code)
        if payload is None:
            return None
        return AhqAuthorizationCode(
            code=authorization_code,
            scopes=payload.get("scopes") or [],
            expires_at=payload["exp"],
            client_id=payload["client_id"],
            code_challenge=payload["code_challenge"],
            redirect_uri=payload["redirect_uri"],
            redirect_uri_provided_explicitly=payload["redirect_uri_provided_explicitly"],
            ahq_token=payload["ahq_token"],
            org_id=payload.get("org_id", ""),
            project_id=payload.get("project_id", ""),
            base_url=payload.get("base_url", ""),
        )

    def _issue_tokens(
        self, client_id: str, ahq_token: str, org_id: str, project_id: str, scopes: list[str],
        base_url: str = "",
    ) -> OAuthToken:
        fields = {
            "ahq_token": ahq_token,
            "org_id": org_id,
            "project_id": project_id,
            "base_url": base_url,
            "client_id": client_id,
            "scopes": scopes,
        }
        access_ttl = _capped_ttl(ahq_token, ACCESS_TTL)
        return OAuthToken(
            access_token=self.codec.encode("access", fields, access_ttl),
            refresh_token=self.codec.encode("refresh", fields, _capped_ttl(ahq_token, REFRESH_TTL)),
            token_type="Bearer",
            expires_in=access_ttl,
            scope=" ".join(scopes) if scopes else None,
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AhqAuthorizationCode
    ) -> OAuthToken:
        org_id = authorization_code.org_id or decode_ahq_token(
            authorization_code.ahq_token).get("organizationId", "")
        if not org_id:
            raise TokenError(error="invalid_grant", error_description="embedded AHQ token has no organization")
        return self._issue_tokens(
            client_id=authorization_code.client_id,
            ahq_token=authorization_code.ahq_token,
            org_id=org_id,
            project_id=authorization_code.project_id,
            scopes=authorization_code.scopes,
            base_url=authorization_code.base_url,
        )

    # --- Refresh (rotates both tokens) ---

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> AhqRefreshToken | None:
        payload = self.codec.decode("refresh", refresh_token)
        if payload is None:
            return None
        return AhqRefreshToken(
            token=refresh_token,
            client_id=payload["client_id"],
            scopes=payload.get("scopes") or [],
            expires_at=payload["exp"],
            ahq_token=payload["ahq_token"],
            org_id=payload.get("org_id", ""),
            project_id=payload.get("project_id", ""),
            base_url=payload.get("base_url", ""),
        )

    async def exchange_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: AhqRefreshToken, scopes: list[str]
    ) -> OAuthToken:
        return self._issue_tokens(
            client_id=refresh_token.client_id,
            ahq_token=refresh_token.ahq_token,
            org_id=refresh_token.org_id,
            project_id=refresh_token.project_id,
            scopes=scopes,
            base_url=refresh_token.base_url,
        )

    # --- Resource-server side ---

    async def load_access_token(self, token: str) -> AhqAccessToken | None:
        payload = self.codec.decode("access", token)
        if payload is None:
            return None
        return AhqAccessToken(
            token=token,
            client_id=payload["client_id"],
            scopes=payload.get("scopes") or [],
            expires_at=payload["exp"],
            ahq_token=payload["ahq_token"],
            org_id=payload.get("org_id", ""),
            project_id=payload.get("project_id", ""),
            base_url=payload.get("base_url", ""),
        )

    async def revoke_token(self, token) -> None:
        # Self-contained tokens can't be individually revoked without storage; see module
        # docstring for why the AHQ-token backstop makes this acceptable. Revocation is
        # disabled in the advertised metadata (RevocationOptions(enabled=False)).
        return None


class AhqTokenVerifier:
    """SDK TokenVerifier protocol implementation for the /mcp resource side."""

    def __init__(self, provider: StatelessAhqProvider):
        self._provider = provider

    async def verify_token(self, token: str) -> AhqAccessToken | None:
        return await self._provider.load_access_token(token)
