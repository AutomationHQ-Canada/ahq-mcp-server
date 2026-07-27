# Deploying / Installing ahq-mcp-server

Two ways to use this server with Claude Code. Both give you the same 115 MCP tools; the plugin
additionally installs the curated workflow skills.

> **Just want to install and use it?** Follow the step-by-step handover guide in
> [`INSTALL.md`](INSTALL.md) — validated end-to-end, with troubleshooting. The sections below
> are the condensed reference.
>
> **Using Claude Desktop, claude.ai, VS Code, Cursor, or Windsurf instead of Claude Code?** No
> install needed — see [`CONNECT.md`](CONNECT.md) for the step-by-step connector guide.

## Option A — Claude Code plugin (recommended)

The repo doubles as a Claude Code plugin (`.claude-plugin/plugin.json` + `skills/*/SKILL.md` +
`.mcp.json`). Installing it registers the MCP server AND the 8 workflow skills
(`/ahq-test-architecture`, `/ahq-gen-from-url`, `/ahq-gen-from-requirements`, `/ahq-run-bot`,
`/ahq-schedule-bot`, `/ahq-view-report`, `/ahq-view-performance`, `/ahq-dashboard`) in one step —
no matter which directory you're working in.

```
/plugin marketplace add AutomationHQ-Canada/ahq-mcp-server
/plugin install ahq-skills@automationhq
```

(The repo is live at https://github.com/AutomationHQ-Canada/ahq-mcp-server — public; no GitHub
login or org membership required.)

Prerequisites on the machine:
1. [`uv`](https://docs.astral.sh/uv/) on PATH — the plugin launches via `uv run`, which
   auto-installs all Python dependencies (pinned by `uv.lock`) on first start. No separate
   Python install or `pip install` needed.
2. `uv run playwright install chromium` — one-time browser download for the `crawl_url` tool,
   and again after any playwright version bump (the package and browser build must match;
   playwright is pinned to a minor version in `pyproject.toml` for exactly this reason).
   Skippable if you never crawl.
3. A `.env` in the plugin root with `AHQ_API_TOKEN` (an ORGANIZATION token from
   Administration → Settings → API Tokens) and `AHQ_PROJECT_ID`. `AHQ_BASE_URL` is optional —
   the gateway URL is normally decoded from the token itself, see INSTALL.md. `.env` is never
   committed.

## Option B — plain MCP server registration (no skills)

From this repo's checkout:

```
claude mcp add ahq-mcp-server -- python -m src.mcp_server
```

or add to any project's `.mcp.json`:

```json
{
  "mcpServers": {
    "ahq-mcp-server": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "C:/path/to/ahq-mcp-server"
    }
  }
}
```

This gives raw tools only — the skills' workflow discipline (always resolve real
templateIds, story_id required, vault-vs-literal credential prompts, ...) lives in the plugin
skills and `CLAUDE.md`, so prefer Option A for anyone not working inside this repo.

## Option C — hosted remote MCP server (Slice 9m, 2026-07-14)

`src/http_server.py` (`ahq-mcp-http` entrypoint) serves the same tools over Streamable HTTP
for the centrally-hosted deployment at `{AHQ_MCP_PUBLIC_BASE_URL}` (dev:
`https://api-dev.automationhq.ai/ahq-mcp-server`). End users install NOTHING — they connect
any MCP client to `{public base}/mcp` and authenticate one of two ways:

**1. OAuth (Claude Desktop / claude.ai connectors, MCP Inspector, any OAuth-capable client).**
The service is its own OAuth 2.1 authorization server (AHQ has none): dynamic client
registration + PKCE, with a browser consent page where the user pastes their AHQ
ORGANIZATION API token once and picks a project (validated live against the gateway — the
Slice 9k org↔project check). All OAuth state (client_id, code, access/refresh tokens) is a
Fernet-encrypted self-contained blob keyed by `AHQ_MCP_AUTH_SECRET` — no storage, any replica
can serve any step. Tokens can't be individually revoked (no storage); the backstop is that
every downstream call carries the user's embedded AHQ token, which the gateway re-validates
against Mongo per request.

**2. Headers (Cursor / VS Code / Claude Code without OAuth).** Same as before: send
`X-API-AUTH-KEY: <org token>` and `projectId: <project id>` on every request. Example
`.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "ahq": {
      "url": "https://api-dev.automationhq.ai/ahq-mcp-server/mcp",
      "headers": { "X-API-AUTH-KEY": "<org token>", "projectId": "<project id>" }
    }
  }
}
```

The 8 workflow skills are also served as **MCP prompts** (`src/prompts.py`), so hosted
clients get the curated workflows without the plugin.

Hosted env vars (see the Helm chart `values-*.yaml` + Secret):

| Var | Where | Notes |
|---|---|---|
| `AHQ_BASE_URL` | ConfigMap | gateway URL the server calls AHQ through |
| `AHQ_MCP_PUBLIC_BASE_URL` | ConfigMap | public URL incl. `/ahq-mcp-server` prefix |
| `AHQ_MCP_AUTH_SECRET` | **Secret** `ahq-mcp-server-secrets` | REQUIRED; identical on every replica; startup fails without it |
| `AHQ_MCP_RATE_LIMIT_PER_MIN` | ConfigMap | per-org token bucket, default 60 |
| `AHQ_MCP_CRAWL_CONCURRENCY` | ConfigMap | max simultaneous headless Chromium, default 2 |

Hardening baked in: per-org rate limiting, 2 MB request-body cap, one JSON audit line per
tool call (org/project/tool/duration/ok — never arguments), SSRF guard on hosted crawls
(private/metadata addresses blocked per navigation). `crawl_url` IS available hosted
(Chromium is baked into the Docker image); `extract_requirements` and
`check_local_agent_status` remain stdio-only.

Deploy prerequisites (DevOps): ECR repo `ahq-mcp-server`; k8s Secret `ahq-mcp-server-secrets`
with a random ≥64-char `AHQ_MCP_AUTH_SECRET`; chart from `deploy/argocd-chart-draft/` adopted
into kubernetes-argocd-apps; gateway change making `/ahq-mcp-server/**` permitAll (like
`testbot-mcp-server` — OAuth Bearer tokens we issue can't pass the gateway's own auth).

## Note on `skills/` vs `.claude/skills/`

`skills/<name>/SKILL.md` is the plugin-distribution layout (what `/plugin install` picks up).
`.claude/skills/*.md` is the repo-local layout that works when working inside this repo.
They are the same content — when editing a skill, edit BOTH copies (or edit `.claude/skills/`
and re-copy) until the repo-local copies are retired.
