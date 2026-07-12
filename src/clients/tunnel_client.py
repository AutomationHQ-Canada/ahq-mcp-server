from src.clients.base_client import BaseAhqClient

TUNNEL_CLIENT_ID = "ahq-mcp-server"


class TunnelClient(BaseAhqClient):
    """
    Tunnel endpoints live on ahq-gateway-services ITSELF — served at the gateway root with no
    /ahq-xxx-services prefix to strip, hence the empty service_prefix (unique among clients).

    Only 4 operations exist server-side (TunnelController + TunnelLauncherController):
    status / start / stop / execute. CLAUDE.md's original "Tunnel Commands" list also named
    restart/health/info/logs/version — those are NOT implemented anywhere in the gateway and
    never were; do not add tools for them.
    """

    def __init__(self, credentials=None, http_client=None):
        super().__init__("", credentials, http_client)

    async def _tunnel_auth(self) -> dict:
        # Every tunnel endpoint is @PreAuthorize("hasRole('TUNNEL_CLIENT')") — the ORGANIZATION
        # API token (ROLE_SITE_ADMIN/ROLE_AHQ_SUPPORT) does NOT carry that role, so the default
        # X-API-AUTH-KEY header alone always 403s. The gateway mints a short-lived (1h) tunnel
        # JWT via POST /token/tunnel; minted fresh per call rather than cached, so expiry can
        # never surface as a confusing mid-session 401.
        r = await self.post("/token/tunnel", params={"clientId": TUNNEL_CLIENT_ID})
        token = r.get("tunnelToken") if isinstance(r, dict) else None
        if not token:
            raise RuntimeError(f"Gateway did not return a tunnelToken: {str(r)[:200]}")
        return {"Authorization": f"Bearer {token}"}

    async def get_tunnel_status(self) -> dict:
        # /tunnel-launcher/status reports the actual tunnel PROCESS state; /tunnel/status is just
        # a static auth-probe string ("Tunnel is Active and Authenticated"), so it adds nothing.
        return await self.get("/tunnel-launcher/status", extra_headers=await self._tunnel_auth())

    async def start_tunnel(self) -> dict:
        # startTunnel() reads the Bearer token back OUT of the Authorization header to hand to
        # the tunnel process — the same header used for auth does double duty.
        return await self.post("/tunnel-launcher/start", extra_headers=await self._tunnel_auth())

    async def stop_tunnel(self) -> dict:
        return await self.post("/tunnel-launcher/stop", extra_headers=await self._tunnel_auth())

    async def execute_tunnel_command(self, command: str) -> dict:
        # @RequestBody String — a raw string body, not a JSON object.
        return await self.post(
            "/tunnel/execute", content=command, extra_headers=await self._tunnel_auth()
        )
