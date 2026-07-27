# Installing the AutomationHQ Claude Code Plugin (ahq-skills)

Follow this guide to connect Claude Code to AutomationHQ. You get **136 MCP tools** (script
generation, bot execution, reporting, version control, archive, roles, API/load testing, ...)
plus **9 workflow skills** (`/ahq-test-architecture`, `/ahq-gen-from-url`,
`/ahq-gen-from-requirements`, `/ahq-heal-locators`, `/ahq-run-bot`, `/ahq-schedule-bot`,
`/ahq-view-report`, `/ahq-view-performance`, `/ahq-dashboard`).

Total time: ~10 minutes. Every step below was validated end-to-end on Windows on 2026-07-13.

> Don't want to install anything? Any MCP client (Claude Desktop, claude.ai, VS Code, Cursor,
> Windsurf) can connect to the hosted server with just a URL — see [`CONNECT.md`](CONNECT.md)
> for the step-by-step connector guide. This guide is for the Claude Code plugin (stdio) setup.

---

## Prerequisites

| Requirement | How to check | How to get it |
|---|---|---|
| Claude Code v2+ | `claude --version` | https://claude.com/claude-code |
| `uv` on PATH | `uv --version` | Windows: `winget install astral-sh.uv` · macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh \| sh` — no Python install needed, uv brings its own |
| An AHQ **ORGANIZATION** API token | — | AHQ UI → Administration → Settings → API Tokens (ask your admin if you can't create one) |

> The `ahq-mcp-server` repo is public, so `/plugin marketplace add` in Step 1 works with no
> GitHub login required. If it still fails with a git error, install `git` and retry.

## Step 1 — Add the marketplace

In any Claude Code session (any directory):

```
/plugin marketplace add AutomationHQ-Canada/ahq-mcp-server
```

Expected output: `Successfully added marketplace: automationhq`

## Step 2 — Install the plugin

```
/plugin install ahq-skills@automationhq
```

When asked for a scope, pick **"Install for you (user scope)"** — this makes the plugin
available in every project/directory on your machine.

## Step 3 — One-time setup (dependencies + credentials)

The plugin clones itself to a fixed location:

```
%USERPROFILE%\.claude\plugins\cache\automationhq\ahq-skills\<version>\
```

(e.g. `C:\Users\<you>\.claude\plugins\cache\automationhq\ahq-skills\0.2.1` — **the last folder is
the plugin version; check which one exists and use that in the commands below**).

The server launches via `uv run`, which **installs all Python dependencies automatically on the
first launch** (pinned by `uv.lock`, isolated from your system Python) — there is nothing to
`pip install`. The only setup is your credentials file, and the recommended place for it is the
**stable, version-independent** `~/.ahq/.env` — the server checks it on every start, and it
**survives plugin upgrades** (a `.env` placed inside a plugin version folder dies with that
folder on the next update):

**Windows (PowerShell):**

```powershell
mkdir $env:USERPROFILE\.ahq -Force
notepad $env:USERPROFILE\.ahq\.env   # fill in the two values below
```

**macOS / Linux:**

```bash
mkdir -p ~/.ahq
nano ~/.ahq/.env   # fill in the two values below
```

> **No browser install needed.** `crawl_url` and `heal_locator` drive a real Chromium, and the
> first call to either downloads it automatically (~150 MB, a few minutes, once per
> environment — including after a playwright version bump, since the package and browser build
> are version-locked). Nobody who only runs bots and reads reports ever downloads it. To
> pre-warm it instead of paying that cost mid-request, run `uv run playwright install chromium`
> from the plugin folder.

> A `.env` inside the plugin version folder (or real environment variables `AHQ_API_TOKEN` etc.)
> also works and overrides `~/.ahq/.env` — precedence: env vars > plugin-folder `.env` >
> `~/.ahq/.env`. Use those only when you deliberately want a per-version or per-shell override.

> The very first session start after installing/updating takes a little longer while `uv`
> resolves and installs dependencies; every start after that is instant (cached).

Your `.env` needs two values:

```
AHQ_API_TOKEN=<your ORGANIZATION token from Administration -> Settings -> API Tokens>
AHQ_PROJECT_ID=<the UUID of the project to work in>
```

> **Where to find `AHQ_PROJECT_ID`:** open the AHQ web UI and enter your project — the browser
> URL is `dev.automationhq.ai/<orgId>/<projectId>/...`; the **second** UUID is the project ID.
>
> **Note:** Your org ID **and** the API gateway URL are both decoded from the token automatically
> (from its `organizationId` and `urlDetails.baseUrl` claims) — do not add either. `AHQ_BASE_URL`
> is optional now and only used as a fallback for a token that predates the `urlDetails` claim;
> set it (to the **API gateway**, e.g. `https://api-dev.automationhq.ai` — NOT the web UI) only if
> `/mcp` reports the token has no usable base URL. The `LLM_API_KEY` line in `.env.example` is
> currently unused — leave it or delete it.

## Step 4 — Verify

1. **Restart Claude Code** (or run `/reload-plugins`) — the MCP server starts with the session
   (first start installs dependencies, give it a moment).
2. Run `/mcp` → `ahq-mcp-server` should show **connected** with 136 tools.
3. Type `/ahq` → the 9 skills should autocomplete. Plugin skills are **namespaced**, so the full
   names are `/ahq-skills:ahq-dashboard`, `/ahq-skills:ahq-gen-from-url`, etc.
4. Smoke test — ask Claude: *"list my AHQ websites"*. Real data back = you're done.

> Don't be alarmed if `/reload-plugins` reports `0 skills` — that counter only covers standalone
> (non-plugin) skills. Verify with `claude plugin details ahq-skills@automationhq` in a terminal:
> it should list **Skills (9)** and **MCP servers (1)**.

## Updating to a newer version

In Claude Code (or a terminal with `claude plugin ...`):

```
/plugin marketplace update automationhq
/plugin update ahq-skills@automationhq
```

Then restart the session (or `/reload-plugins`) — that's it. If your credentials live in
`~/.ahq/.env` (the recommended setup), **nothing else is needed**: the new version finds them
automatically. Only if you keep a `.env` inside the plugin version folder do you have to copy it
into the new folder yourself.

If the playwright version changed (see `pyproject.toml`) the new package needs a matching browser
build. The first `crawl_url`/`heal_locator` call after the upgrade fetches it automatically; run
`uv run playwright install chromium` from the new plugin folder only if you'd rather pay that
cost up front.

## Troubleshooting

Since v0.1.1 the server fails **loudly** on misconfiguration: a tool call with a missing/empty
`.env` returns an error naming the exact variable and the exact path where `.env` is expected —
read that message first, it usually IS the fix.

| Symptom | Cause / fix |
|---|---|
| `marketplace add` fails with a clone error | The repo is public, so this is usually just a missing/misconfigured local `git` install — install `git`, then retry. |
| Tool errors say `ahq-mcp-server is not configured: ... is empty` | The `.env` is missing, in the wrong folder, or missing a value — the message names the variable and the expected file path. Fix, then `/reload-plugins`. |
| Tool errors say `Got the web frontend's HTML instead of an API response` | The gateway URL is normally decoded from your token automatically. This means either your token predates the `urlDetails` claim (add `AHQ_BASE_URL` to `.env`, pointed at the API gateway, e.g. `https://api-dev.automationhq.ai`, never the web UI) or an `AHQ_BASE_URL` override you added yourself points at the web UI — remove or fix it. |
| `/mcp` shows `ahq-mcp-server` **failed** | Usually `uv` missing from PATH (`uv --version` to check; restart the terminal/session after installing it). Verify the server itself with: `uv run --project <plugin folder> python -c "from src.mcp_server import TOOLS; print(len(TOOLS))"` → must print `136`. |
| Tools work but `/ahq` skills don't appear | Restart the Claude Code session — skills register at startup. Full names are namespaced: `/ahq-skills:ahq-dashboard`. |
| Every AHQ call returns 401 | Wrong/expired token in `.env`, or you used a personal JWT instead of an ORGANIZATION token. |
| `crawl_url` errors about a missing browser | Since v1.6.8 the first crawl downloads Chromium itself, so this should self-resolve — the first one just takes a few minutes. The error only remains if that download failed (no disk space, no network), and it quotes the real reason. Manual fallback: `uv run playwright install chromium` in the plugin folder. |
| Data lands in the wrong org | Impossible via token alone — org ID is decoded from the token. Check you were given a token for the right organization. |

## For developers (working ON the server, not just using it)

Don't develop inside the plugin cache folder — clone the repo instead:

```powershell
git clone https://github.com/AutomationHQ-Canada/ahq-mcp-server
```

See `DEPLOYMENT.md` (Option B) for registering your checkout as the MCP server, `CLAUDE.md` for
the full platform contract/gotchas reference, and `evals/README.md` for the live golden-task
suite. Branch + PR for all changes — no direct pushes to the default branch.

*Since v0.2.1 the plugin launches via [`uv`](https://docs.astral.sh/uv/) — dependencies install
themselves on first run, pinned by `uv.lock`, isolated from your system Python. Only your `.env`
remains manual, since credentials are personal.*
