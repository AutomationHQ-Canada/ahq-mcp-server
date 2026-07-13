# Installing the AutomationHQ Claude Code Plugin (ahq-skills)

Follow this guide to connect Claude Code to AutomationHQ. You get **115 MCP tools** (script
generation, bot execution, reporting, version control, archive, roles, API/load testing, ...)
plus **7 workflow skills** (`/ahq-gen-from-url`, `/ahq-gen-from-requirements`, `/ahq-run-bot`,
`/ahq-schedule-bot`, `/ahq-view-report`, `/ahq-view-performance`, `/ahq-dashboard`).

Total time: ~10 minutes. Every step below was validated end-to-end on Windows on 2026-07-13.

---

## Prerequisites

| Requirement | How to check | How to get it |
|---|---|---|
| Claude Code v2+ | `claude --version` | https://claude.com/claude-code |
| Python 3.12+ on PATH | `python --version` | https://python.org (check "Add to PATH" during install) |
| GitHub access to `AutomationHQ-Canada` | `gh auth status` | `gh auth login` — the repo is private, so your GitHub account must be in the org |
| An AHQ **ORGANIZATION** API token | — | AHQ UI → Administration → Settings → API Tokens (ask your admin if you can't create one) |

> If `/plugin marketplace add` fails with a git auth error in Step 1, run `gh auth setup-git`
> once in a terminal and retry.

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

(e.g. `C:\Users\<you>\.claude\plugins\cache\automationhq\ahq-skills\0.1.0`). The MCP server is a
Python process launched from that folder with your system `python`, so it needs its dependencies
installed and your credentials placed there — once per machine. Day-to-day use after this needs
nothing; you only repeat it (in the new version folder) after a plugin version update.

**Windows (PowerShell):**

```powershell
cd $env:USERPROFILE\.claude\plugins\cache\automationhq\ahq-skills\0.1.0

# 1. Install Python dependencies
python -m pip install .

# 2. Create your .env (never committed, personal to you)
copy .env.example .env
notepad .env   # fill in the three values below

# 3. OPTIONAL — only if you'll use crawl_url (generate scripts by crawling a live URL)
playwright install chromium
```

**macOS / Linux:**

```bash
cd ~/.claude/plugins/cache/automationhq/ahq-skills/0.1.0

# 1. Install Python dependencies
python3 -m pip install .

# 2. Create your .env (never committed, personal to you)
cp .env.example .env
nano .env   # fill in the three values below

# 3. OPTIONAL — only if you'll use crawl_url (generate scripts by crawling a live URL)
playwright install chromium
```

Your `.env` needs exactly three values:

```
AHQ_BASE_URL=https://api-dev.automationhq.ai
AHQ_API_TOKEN=<your ORGANIZATION token from Administration -> Settings -> API Tokens>
AHQ_PROJECT_ID=<the UUID of the project to work in>
```

> **Where to find `AHQ_PROJECT_ID`:** open the AHQ web UI and enter your project — the browser
> URL is `dev.automationhq.ai/<orgId>/<projectId>/...`; the **second** UUID is the project ID.
>
> **Note:** `AHQ_BASE_URL` is the **API gateway** (`api-dev.automationhq.ai`), NOT the web UI
> (`dev.automationhq.ai`). Your org ID is decoded from the token automatically — do not add it.
> The `LLM_API_KEY` line in `.env.example` is currently unused — leave it or delete it.

## Step 4 — Verify

1. **Restart Claude Code** (or run `/reload-plugins`) — the MCP server starts with the session.
2. Run `/mcp` → `ahq-mcp-server` should show **connected** with 115 tools.
3. Type `/ahq` → the 7 skills should autocomplete. Plugin skills are **namespaced**, so the full
   names are `/ahq-skills:ahq-dashboard`, `/ahq-skills:ahq-gen-from-url`, etc.
4. Smoke test — ask Claude: *"list my AHQ websites"*. Real data back = you're done.

> Don't be alarmed if `/reload-plugins` reports `0 skills` — that counter only covers standalone
> (non-plugin) skills. Verify with `claude plugin details ahq-skills@automationhq` in a terminal:
> it should list **Skills (7)** and **MCP servers (1)**.

## Updating to a newer version

```
/plugin marketplace update automationhq
```

then reinstall/update the plugin from `/plugin`. After an update, repeat Step 3 in the **new**
version folder (new version = new folder under `...\ahq-skills\`), including re-copying your
`.env`. If the playwright version changed (see `pyproject.toml`), run
`playwright install chromium` again — the pip package and browser build must match.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `marketplace add` fails with auth/clone error | `gh auth setup-git`, then retry. Your GitHub account must have access to the private repo. |
| `/mcp` shows `ahq-mcp-server` **failed** | Step 3 was skipped or done in the wrong folder — deps and `.env` must be in the plugin's cache folder shown above, NOT a dev checkout. Verify with: `cd <plugin folder>` then `python -c "from src.mcp_server import TOOLS; print(len(TOOLS))"` → must print `115`. |
| Tools work but `/ahq` skills don't appear | Restart the Claude Code session — skills register at startup. |
| Every AHQ call returns 401 | Wrong/expired token in `.env`, or you used a personal JWT instead of an ORGANIZATION token. |
| `crawl_url` errors about a missing browser | Run `playwright install chromium` (Step 3.3). Required again after any playwright version bump. |
| Data lands in the wrong org | Impossible via token alone — org ID is decoded from the token. Check you were given a token for the right organization. |

## For developers (working ON the server, not just using it)

Don't develop inside the plugin cache folder — clone the repo instead:

```powershell
git clone https://github.com/AutomationHQ-Canada/ahq-mcp-server
```

See `DEPLOYMENT.md` (Option B) for registering your checkout as the MCP server, `CLAUDE.md` for
the full platform contract/gotchas reference, and `evals/README.md` for the live golden-task
suite. Branch + PR for all changes — no direct pushes to the default branch.

## Planned enhancement

A future version will switch the plugin to launch via [`uv`](https://docs.astral.sh/uv/), which
auto-installs dependencies on first run — removing Step 3.1 entirely. Steps 3.2 (your `.env`)
will remain, since credentials are personal.
