import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The directory containing pyproject.toml / .env — resolved from this file's location, NOT the
# process cwd. Claude Code (and other MCP clients) launch the server with an arbitrary cwd (in
# practice the user's project directory), so a cwd-relative env_file=".env" silently finds
# nothing and the server runs with empty credentials against the default URL — every tool then
# "succeeds" with the web app's HTML instead of API data. Found live during the first teammate
# plugin install (2026-07-13).
REPO_ROOT = Path(__file__).resolve().parents[2]


def _env_file_candidates() -> tuple[str, ...]:
    # Ordered lowest→highest precedence (pydantic-settings: later files win); real environment
    # variables (AHQ_API_TOKEN etc.) beat every file:
    #   1. ~/.ahq/.env — stable, version-INDEPENDENT credentials home. Each plugin version
    #      installs into a fresh folder with no .env, so credentials placed only inside a plugin
    #      folder die on every upgrade (bit a user live, 2026-07-13). This path survives.
    #   2. next to this package (repo checkout, or the plugin root when run via `-m` from there)
    #   3. AHQ_MCP_HOME — set by the plugin's .mcp.json to ${CLAUDE_PLUGIN_ROOT}; covers the
    #      pip-installed case where this file lives in site-packages and (2) points nowhere useful
    #   4. process cwd, as a manual override
    candidates = [str(Path.home() / ".ahq" / ".env"), str(REPO_ROOT / ".env")]
    mcp_home = os.environ.get("AHQ_MCP_HOME")
    if mcp_home:
        candidates.append(str(Path(mcp_home) / ".env"))
    candidates.append(".env")
    return tuple(candidates)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_file_candidates(),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # No default on purpose: the only guessable value would be the web frontend, which is never
    # correct for API calls. Empty + the fail-fast guard in mcp_server beats silently wrong.
    ahq_base_url: str = ""
    # Required for stdio mode (loaded from .env); left empty in hosted HTTP mode, where every
    # request supplies its own credentials via headers (AhqCredentials.from_headers) instead —
    # the container itself never holds a single tenant's token/project.
    ahq_api_token: str = ""
    # No ahq_org_id here on purpose — org_id is always derived from the token's own
    # organizationId claim (see AhqCredentials.from_settings), never independently configured.
    # A stale/mismatched org_id here would silently write real data into the wrong organization,
    # since the gateway doesn't validate that a request's org-id header matches the token's claim.
    ahq_project_id: str = ""
    llm_api_key: str = ""
    # Grace period check_local_agent_status waits out the first time it sees the local agent
    # online, before reporting ready — the agent's own async startup (token revalidation,
    # chromedriver resolution) can still be in progress even though it already answers /ping.
    # Stdio-only (check_local_agent_status is unavailable in hosted mode).
    ahq_local_agent_warmup_seconds: int = 15

    # --- Hosted (HTTP) mode only — all defaulted so stdio users and tests never notice them ---
    # Public URL this service is reachable at THROUGH the gateway, including the route prefix
    # (StripPrefix removes it before requests reach us, but every URL we advertise to OAuth
    # clients must include it), e.g. https://api-dev.automationhq.ai/ahq-mcp-server.
    # Empty -> http://localhost:8000 for local development.
    ahq_mcp_public_base_url: str = ""
    # Fernet passphrase for the stateless OAuth blobs (client_id / code / access / refresh).
    # REQUIRED in hosted mode and must be identical across replicas — ahq-mcp-http fails fast at
    # startup if empty. Never used in stdio mode.
    ahq_mcp_auth_secret: str = ""
    ahq_mcp_rate_limit_per_min: int = 60
    ahq_mcp_max_body_bytes: int = 2_000_000
    # Extra allowed OAuth redirect URIs beyond loopback + the Claude callbacks, comma-separated
    # (e.g. a future Cursor/Windsurf deep-link scheme).
    ahq_mcp_extra_redirect_uris: str = ""
    ahq_mcp_crawl_concurrency: int = 2
    # Frontend-hosted consent page (automationhq-frontend-v2's real design system) to redirect to
    # instead of our own bare-HTML /consent page, e.g. https://dev.automationhq.ai/mcp-consent.
    # Empty -> falls back to the built-in HTML page (local/stdio testing, or before this is wired).
    ahq_mcp_consent_frontend_url: str = ""
    # Extra allowed AHQ gateway base URLs a token's own urlDetails.baseUrl claim may resolve to,
    # beyond the two known hosts (dev/prod — see credentials.KNOWN_BASE_URLS), comma-separated
    # (e.g. a future staging environment).
    ahq_mcp_extra_base_urls: str = ""

    def extra_base_urls(self) -> frozenset[str]:
        return frozenset(u.strip() for u in self.ahq_mcp_extra_base_urls.split(",") if u.strip())


# Gateway prefix constants — StripPrefix=1 removes these before forwarding
ASSET_SVC         = "/ahq-asset-services"
TEST_MGMT_SVC     = "/ahq-test-management-services"
BACKGROUND_SVC    = "/ahq-background-v2-services"
CONFIG_SVC        = "/ahq-config-services"
USER_MGMT_SVC     = "/ahq-user-management-services"
EXECUTOR_SVC      = "/ahq-test-bot-executor-services"
LOCAL_EXEC_SVC    = "/test-local-execution-services"  # NOT gateway-routed — runs on the user's machine, see local_exec_client.py
STANDALONE_SVC    = "/ahq-standalone-local-v2-services"
MANAGED_TEST_SVC  = "/mtaf-core"          # gateway route id, NOT the repo name "managed-testing-service-core"
VIRT_CLIENT_SVC   = "/mtaf-sv-client"     # gateway route id, NOT the repo name "managed-testing-virtualization-client"
VIRT_SERVER_SVC   = "/mtaf-sv-server"     # gateway route id, NOT the repo name "managed-testing-virtualization-server"
CDCT_SVC          = "/mtaf-cdct"          # gateway route id, NOT the repo name "mtaf-cdct-core"
AUTH_SVC          = "/ahq-auth-services"
EMAIL_SVC         = "/ahq-email-v2-services"


settings = Settings()
