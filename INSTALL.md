# Installing the AutomationHQ Claude Code Plugin (ahq-skills)

Follow this guide to connect Claude Code to AutomationHQ. You get **136 MCP tools** (script
generation, bot execution, reporting, version control, archive, roles, API/load testing, ...)
plus **9 workflow skills** (`/ahq-test-architecture`, `/ahq-gen-from-url`,
`/ahq-gen-from-requirements`, `/ahq-heal-locators`, `/ahq-run-bot`, `/ahq-schedule-bot`,
`/ahq-view-report`, `/ahq-view-performance`, `/ahq-dashboard`).

Total time: about 10 minutes.

> **Don't want to install anything?** Claude Desktop, claude.ai, VS Code, Microsoft Copilot,
> Lovable, Cursor and Windsurf can all connect to the hosted server with just a URL — see
> [`CONNECT.md`](CONNECT.md).
>
> Choose this plugin instead when you need either of the two things a URL connection cannot do:
> run tests on a **test agent on your own machine**, or use the **guided workflow skills**.

---

## Quick start

Everything, in order. Details and troubleshooting are below if you need them.

**1. Install `uv`** — once per machine, in a terminal:

```powershell
winget install astral-sh.uv                        # Windows
curl -LsSf https://astral.sh/uv/install.sh | sh    # macOS / Linux
```

**2. Install the plugin** — in Claude Code:

```
/plugin marketplace add AutomationHQ-Canada/ahq-mcp-server
/plugin install ahq-skills@automationhq
```

Choose **"Install for you (user scope)"**.

**3. Add your credentials** — in a terminal:

```powershell
mkdir $env:USERPROFILE\.ahq -Force                 # Windows
notepad $env:USERPROFILE\.ahq\.env

mkdir -p ~/.ahq                                    # macOS / Linux
nano ~/.ahq/.env
```

Put two lines in that file:

```
AHQ_API_TOKEN=<your ORGANIZATION token>
AHQ_PROJECT_ID=<your project UUID>
```

Token: AHQ → **Administration → Settings → API Tokens → Create**, type **Organization**.
Project UUID: the **second** UUID in the AHQ web app's URL.

**4. Restart Claude Code**, then check:

```
/mcp        →  ahq-mcp-server: connected, 136 tools
/ahq        →  9 skills autocomplete
```

Ask *"list my AHQ websites"*. Real data back means you're done.

> Nothing else to install — no Python, no `pip`, no browser download. `uv` brings its own Python,
> dependencies install on first launch, and Chromium downloads itself the first time you crawl a
> URL (if you ever do).

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

(e.g. `C:\Users\<you>\.claude\plugins\cache\automationhq\ahq-skills\1.6.8` — **the last folder is
the plugin version; check which one exists on your machine and use that below**).

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

> **Where to find `AHQ_PROJECT_ID`:** open the AHQ web app and enter your project — the browser
> URL is `<host>/<orgId>/<projectId>/...`; the **second** UUID is the project ID.
>
> **Don't add anything else.** Your organization ID and the API gateway URL are both decoded from
> the token itself. `AHQ_BASE_URL` is only needed as a fallback for an older token, and only if
> `/mcp` reports the token has no usable base URL — if you do set it, point it at the **API
> gateway** (e.g. `https://api-dev.automationhq.ai`), never the web app.

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

---

## Please read before storing credentials in a test script

**Passwords used in test steps appear in plaintext in execution reports.**

AutomationHQ's secret vault keeps a credential out of the stored test script — the step displays
as `Enter [vault: my_password] for "Password field"` and the real value appears nowhere in the
script document. That part works as expected.

When the test runs, however, the executor resolves the secret and writes the **resolved value**
into the execution report:

```
"statusMessage": "Entered value MyRealPassword123"
```

So anyone who can read an execution report can read that credential. The vault protects storage,
not the full lifecycle.

**What to do:** use dedicated test accounts with credentials you're willing to have visible in
report history, and never reuse a production or personal password in a test script. Raise it with
your AutomationHQ contact if report-level protection matters for your use case.

---

## Troubleshooting

The server fails **loudly** on misconfiguration: a tool call with a missing or empty `.env`
returns an error naming the exact variable and the exact path where `.env` is expected — read
that message first, it usually IS the fix.

| Symptom | Cause / fix |
|---|---|
| `marketplace add` fails with a clone error | The repo is public, so this is usually just a missing/misconfigured local `git` install — install `git`, then retry. |
| Tool errors say `ahq-mcp-server is not configured: ... is empty` | The `.env` is missing, in the wrong folder, or missing a value — the message names the variable and the expected file path. Fix, then `/reload-plugins`. |
| Tool errors say `Got the web frontend's HTML instead of an API response` | The gateway URL is normally decoded from your token automatically. This means either your token predates the `urlDetails` claim (add `AHQ_BASE_URL` to `.env`, pointed at the API gateway, e.g. `https://api-dev.automationhq.ai`, never the web UI) or an `AHQ_BASE_URL` override you added yourself points at the web UI — remove or fix it. |
| `/mcp` shows `ahq-mcp-server` **failed** | Usually `uv` missing from PATH (`uv --version` to check; restart the terminal/session after installing it). Verify the server itself with: `uv run --project <plugin folder> python -c "from src.mcp_server import TOOLS; print(len(TOOLS))"` → must print `136`. |
| Tools work but `/ahq` skills don't appear | Restart the Claude Code session — skills register at startup. Full names are namespaced: `/ahq-skills:ahq-dashboard`. |
| Every AHQ call returns 401 | Wrong/expired token in `.env`, or you used a personal JWT instead of an ORGANIZATION token. |
| `crawl_url` errors about a missing browser | The first crawl downloads Chromium itself, so this normally self-resolves — that one call just takes a few minutes. The error only persists if the download actually failed (no disk space, no network), and it quotes the real reason. Manual fallback: `uv run playwright install chromium` in the plugin folder. |
| Data lands in the wrong org | Not possible via the token alone — the org ID is decoded from it. Check you were given a token for the right organization. |
| Assets you created aren't visible in the web app (or vice versa) | Results are scoped to organization **and** project together, and a mismatched pair returns an empty result rather than an error. Check `AHQ_PROJECT_ID` matches the project you're looking at. |

## For developers (working ON the server, not just using it)

Don't develop inside the plugin cache folder — clone the repo instead:

```powershell
git clone https://github.com/AutomationHQ-Canada/ahq-mcp-server
```

See `DEPLOYMENT.md` (Option B) for registering your checkout as the MCP server, `CLAUDE.md` for
the full platform contract/gotchas reference, and `evals/README.md` for the live golden-task
suite. Branch + PR for all changes — no direct pushes to the default branch.

*The plugin launches via [`uv`](https://docs.astral.sh/uv/) — dependencies install themselves on
first run, pinned by `uv.lock` and isolated from your system Python. Only your `.env` stays
manual, since credentials are personal.*
