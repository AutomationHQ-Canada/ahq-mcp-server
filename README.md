# TestBots.ai MCP Server

An [MCP](https://modelcontextprotocol.io) server for the **TestBots.ai** test-automation
platform. It puts the platform behind plain language: ask an AI assistant to crawl an app and
generate test scripts, run a TestBot, read the execution report, heal a locator a UI change
broke, open a pull request — no TestBots.ai web UI needed.

**137 tools** across 18 domains, plus **9 guided workflow skills** for Claude Code.

> **On the name.** The MCP server now identifies itself as `testbots-mcp-server` in `/mcp` output
> and as the prefix on every tool name. Credentials moved with it: `~/.testbots/.env` and
> `TESTBOTS_API_TOKEN` / `TESTBOTS_PROJECT_ID` / `TESTBOTS_BASE_URL`. **Existing installs keep
> working** — `~/.ahq/.env` is still read, and the `AHQ_*` names still resolve, so there is
> nothing you must change. The new names win where both are set.
>
> Still `ahq-`, deliberately: the hosted connector's `/ahq-mcp-server` gateway path, the
> `AHQ_MCP_*` deployment settings, the ECR repository and the k8s resources. Each of those breaks
> a *live* connection or a deploy rather than an install, so they move together with the
> connector URL.

```
"Crawl https://shop.example.com and generate smoke tests for the checkout flow"
"Run the Regression bot on Chrome and tell me what failed"
"Which locators are broken, and can you fix them?"
```

---

## Getting started

Pick the row that matches how you work. All three reach the same tools.

| | Who it's for | What you need | Guide |
|---|---|---|---|
| **Hosted connector** | Claude Desktop, claude.ai, VS Code Copilot, Cursor, Windsurf, Microsoft Copilot Studio, Lovable | A URL and your TestBots.ai login | [`CONNECT.md`](CONNECT.md) |
| **Claude Code plugin** | Claude Code users | [`uv`](https://docs.astral.sh/uv/) and an API token | [`INSTALL.md`](INSTALL.md) |
| **Local checkout** | Developing *on* this server | Python 3.11+, `uv` | [`CONTRIBUTING.md`](CONTRIBUTING.md) |

### Hosted — one URL, nothing to install

Add a custom MCP connector pointing at:

```
https://api-dev.testbots.ai/mcp-server/mcp
```

Leave authentication as **OAuth** (the default). Your browser opens TestBots.ai's sign-in page;
enter the **same email and password you use for the web app**, pick a project, and authorize.
The session then carries your own roles and permissions.

> The `/mcp` suffix is required. The bare service URL returns a plain 404 and OAuth discovery
> never starts, which surfaces in clients as *"couldn't register with the sign-in service"*.

### Claude Code plugin — adds skills and local-agent execution

```
/plugin marketplace add testbots-ai/mcp-server
/plugin install testbots-skills@testbots
```

> **Already had the plugin installed as `ahq-skills@automationhq`?** The plugin was renamed in
> 3.0.0 and an in-place update will not carry you across. Remove the old one first, or you end up
> with both and duplicate slash commands:
>
> ```
> /plugin uninstall ahq-skills@automationhq
> /plugin marketplace remove automationhq
> ```
>
> The slash commands were renamed too — `/ahq-run-bot` is now `/testbots-run-bot`, and so on for
> all nine.

Then sign in — in a **terminal window**, since it prompts for your password:

```powershell
cd (Get-ChildItem $env:USERPROFILE\.claude\plugins\cache\testbots\testbots-skills |
    Sort-Object Name -Descending | Select-Object -First 1).FullName     # Windows
cd "$(ls -d ~/.claude/plugins/cache/testbots/testbots-skills/* | sort -V | tail -1)"  # macOS/Linux

uv run --project . python -m src.login
```

Email, password, pick a project. It creates a one-year API token and writes `~/.testbots/.env` for
you — no visit to the web app, no token to copy, no project UUID to paste. The password is used for
the one sign-in call and is not written anywhere.

Prefer to do it by hand? Put `TESTBOTS_API_TOKEN` (Administration → Settings → API Tokens → Create)
and `TESTBOTS_PROJECT_ID` (the second UUID in the web app's URL) in `~/.testbots/.env` yourself.

Restart Claude Code and check `/mcp`. Choose the plugin over the hosted connector when you need
either of the two things a URL connection cannot do: run tests on a **test agent on your own
machine**, or use the **workflow skills**.

---

## Skills

Guided, multi-step workflows shipped with the plugin. Each one is a slash command.

| Skill | What it does |
|---|---|
| `/testbots-test-architecture` | Crawl a live app, derive modules, lay them out as Epics and Stories |
| `/testbots-gen-from-url` | Generate test scripts by crawling a URL |
| `/testbots-gen-from-requirements` | Generate test scripts from a PDF, DOCX, XLSX, CSV or TXT spec |
| `/testbots-heal-locators` | Find locators broken by a UI change, propose a fix, apply on confirmation |
| `/testbots-run-bot` | Execute a TestBot now and report the result |
| `/testbots-schedule-bot` | Put a TestBot on a recurring cron schedule |
| `/testbots-view-report` | Show the execution report for the last or a specific run |
| `/testbots-view-performance` | Show performance and ROI metrics for a run |
| `/testbots-dashboard` | Project overview — websites, scripts, bots, recent runs, queue state |

---

## Tool surface

| Group | Tools | Covers |
|---|---:|---|
| `context` | 2 | Where am I — current project, and which projects you can reach |
| `discovery` | 9 | Websites, pages, locators, URL crawling |
| `healing` | 3 | Scan for broken locators, propose fixes, apply them |
| `authoring` | 17 | Test scripts, steps, step templates, common functions, recordings |
| `planning` | 8 | Epics, stories, suites, requirement extraction |
| `execution` | 14 | TestBots, grids, browsers, local agents, run status |
| `scheduling` | 7 | Cron schedules and recipients |
| `reporting` | 4 | Execution reports, screenshots, recent runs |
| `versioning` | 14 | Branches, commits, pull requests, review |
| `admin` | 9 | Project roles, members, archive and restore |
| `vault` | 11 | Config vault secrets, environments, global parameters |
| `api` | 11 | API collections and requests, cURL and Postman import |
| `performance` | 5 | Performance bots and their reports |
| `contracts` | 7 | Consumer-driven contract testing (Pact) |
| `mocks` | 5 | Service virtualization mappings |
| `workflows` | 4 | Workflow definitions and test runs |
| `tunnel` | 4 | Secure tunnels to private environments |
| `utility` | 3 | Fake data, email, service specs |

### Trimming the surface

Every tool schema is serialized into the model's context on **every** message — MCP has no lazy
schema loading. At 137 tools that is ~14.5k tokens of fixed overhead per turn, and, more
importantly, 137 near-identical options for the model to choose between.

Set a profile to advertise fewer:

```
AHQ_MCP_TOOL_PROFILE=core        # 57 tools — half the payload, all 9 skills still work
AHQ_MCP_TOOL_PROFILE=core,api    # add a group
```

Group names are the table above; see [`src/tool_groups.py`](src/tool_groups.py). Unset means
all 137.

---

## Configuration

Copy [`.env.example`](.env.example) to `.env`. Never commit it.

| Variable | Required | Notes |
|---|---|---|
| `TESTBOTS_API_TOKEN` | stdio mode | Organization or User token from Administration → Settings → API Tokens |
| `TESTBOTS_PROJECT_ID` | stdio mode | The only credential with no in-token equivalent |
| `TESTBOTS_BASE_URL` | no | Derived from the token's own `urlDetails.baseUrl` claim; set only as a fallback, and only to the API gateway |
| `AHQ_MCP_TOOL_PROFILE` | no | See above |
| `AHQ_LOCAL_AGENT_WARMUP_SECONDS` | no | Default 15 — the local agent's `/ping` answers before its own startup finishes |
| `LLM_API_KEY` | no | For tools that call a model directly |

There is deliberately **no `AHQ_ORG_ID`**. Organization is always read from the token's own
`organizationId` claim — a separately configured one could drift out of sync and silently write
into the wrong organization.

Hosted (`ahq-mcp-http`) mode only:

| Variable | Required | Notes |
|---|---|---|
| `AHQ_MCP_AUTH_SECRET` | **yes** | Seals every OAuth blob. Must be identical across replicas — a mismatch silently invalidates logins |
| `AHQ_MCP_PUBLIC_BASE_URL` | yes | Externally reachable base, including any gateway path prefix |
| `AHQ_MCP_RATE_LIMIT_PER_MIN` | no | Default 60 |
| `AHQ_MCP_MAX_BODY_BYTES` | no | Default 2 MB |
| `AHQ_MCP_PARTNER_DISPLAY_NAME` / `_LOGO_URL` / `_PRIMARY_COLOR` | no | Branding on the sign-in page |

---

## Architecture

```
src/
  mcp_server.py      stdio entrypoint — tool schemas + dispatch (ahq-mcp)
  http_server.py     hosted entrypoint — Starlette app, OAuth routes (ahq-mcp-http)
  tool_groups.py     the 18-group partition behind AHQ_MCP_TOOL_PROFILE
  prompts.py         prompt templates
  clients/           one client per backing service, all on base_client.py
  config/            settings, credentials, gateway route prefixes
  hosted/            OAuth 2.1 provider, consent page, dual auth, rate limit, audit
  tools/             local work — Playwright crawling, locator healing, doc parsing
skills/              9 Claude Code workflow skills
tests/               ~380 tests, pytest + pytest-asyncio
```

A call flows: **assistant → tool dispatch → a service client → the TestBots API gateway → the
owning microservice**. Clients are thin; each maps to one gateway route prefix
(`/ahq-asset-services`, `/ahq-test-management-services`, `/mtaf-core`, and so on — see
[`src/config/ahq_services.py`](src/config/ahq_services.py)).

### Authentication

Which header goes out depends on which credential is in play:

- **API token** (plugin/stdio, and legacy hosted headers) → `X-API-AUTH-KEY`. The gateway
  resolves it by existence lookup, so it reaches everything in the organization regardless of
  who created it.
- **Login JWT** (hosted connector, after email/password sign-in) → `Authorization: Bearer`.
  This is the gateway's user-aware path, so the session carries the signed-in person's roles.

`org-id` and `projectId` are omitted when empty rather than sent blank — an empty `org-id` reads
downstream as *"belongs to organization ''"* and is rejected.

### Hosted mode is stateless

`ahq-mcp-http` is its own OAuth 2.1 authorization server. Client registration, authorization
codes, access tokens and refresh tokens are all encrypted blobs keyed by `AHQ_MCP_AUTH_SECRET`;
nothing is stored, so any replica can serve any step of the flow.

One consequence worth knowing up front: **a connection cannot outlive the credential sealed
inside it.** Both the access and the refresh token are capped at the embedded credential's
expiry — necessarily, since every downstream call re-presents it. When it lapses you re-sign-in
on the consent page. The connector entry and everything you created stay put.

---

## Development

```bash
git clone https://github.com/testbots-ai/mcp-server
cd mcp-server
uv sync --extra dev
uv run playwright install chromium     # only if you'll use crawl_url or locator healing
```

Register the local checkout with Claude Code:

```bash
claude mcp add testbots-mcp-server-dev -- python -m src.mcp_server
```

Run the tests:

```bash
uv run pytest
```

> If a run fails with confusing import errors, set `PYTHONNOUSERSITE=1` — a stale user-site
> `src` package can shadow the repo's own.

Playwright's Python package and its browser build are version-locked, which is why it is pinned
to a minor range in `pyproject.toml`. Bump the pin and re-run `playwright install chromium`
together, never one without the other.

Full developer walkthrough, including verifying against a live environment:
[`CONTRIBUTING.md`](CONTRIBUTING.md).

### Versioning

The plugin updater keys **only** on `.claude-plugin/plugin.json`'s `version` — shipping code
without a bump means plugin users never receive it. Bump both `plugin.json` and `pyproject.toml`
together: PATCH for fixes, MINOR for new tools or skills, MAJOR for breaking tool contracts.
Internal-only changes (CI, tests, design docs) need no bump.

---

## Documentation

| File | For |
|---|---|
| [`CONNECT.md`](CONNECT.md) | Connecting any MCP client to the hosted server |
| [`INSTALL.md`](INSTALL.md) | Installing the Claude Code plugin |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Developing on this repo |
| [`DEPLOYMENT.md`](DEPLOYMENT.md) | Deployment reference |
| [`CLAUDE.md`](CLAUDE.md) | Working context for AI assistants editing this repo |
