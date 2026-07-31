# Developer Guide — Running & Verifying ahq-mcp-server Locally

This is the handover doc for anyone developing **on** this repo (not just using it as a
plugin). If you only want to *use* the server, see [`INSTALL.md`](INSTALL.md) instead.

## Prerequisites

| Requirement | How to check | How to get it |
|---|---|---|
| Python 3.11+ | `python --version` | https://python.org (or let `uv` manage it) |
| [`uv`](https://docs.astral.sh/uv/) on PATH | `uv --version` | Windows: `winget install astral-sh.uv` · macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Claude Code v2+ | `claude --version` | https://claude.com/claude-code |
| An AHQ API token (Organization type) | — | AHQ UI → Administration → Settings → API Tokens |

## 1. Clone and install dependencies

```powershell
git clone https://github.com/AutomationHQ-Canada/ahq-mcp-server
cd ahq-mcp-server
uv sync --extra dev
```

`uv sync` creates `.venv/` and installs everything pinned in `uv.lock`, including the `dev`
extras (`pytest`, `pytest-asyncio`). Nothing needs a separate `pip install`.

## 2. Add credentials

Create a `.env` in the repo root (never commit it — it's already in `.gitignore`):

```
AHQ_API_TOKEN=<your Organization API token>
AHQ_PROJECT_ID=<the project UUID you want to test against>
```

Token: AHQ UI → Administration → Settings → API Tokens → Create.
Project UUID: the **second** UUID in the AHQ web app's URL.

`AHQ_BASE_URL` is optional — the gateway URL is decoded from the token itself; only set it if
`/mcp` reports the token has no usable base URL (see the Troubleshooting table below).

## 3. Register your local checkout with Claude Code

```powershell
claude mcp add ahq-mcp-server-dev -- python -m src.mcp_server
```

Run this from inside the repo directory so the relative module path resolves correctly.
Confirm it's connected:

```
claude mcp list
```

You should see `ahq-mcp-server-dev: python -m src.mcp_server - ✔ Connected`.

> This is a **separate** registration from any `ahq-skills@automationhq` plugin install you may
> also have — the plugin always runs the *published* version, this one runs *your checkout*, so
> both can coexist without conflicting.

## 4. Verify a change before handing it off

There's no compile step in Python — "verify it builds" means deps resolve, imports succeed,
and tests pass.

**a. Run the test suite**

```powershell
uv run pytest
```

**b. Smoke-check the server module loads and the tool registry is intact**

```powershell
uv run python -c "from src.mcp_server import TOOLS; print(len(TOOLS))"
```

A clean number with no traceback means the wiring is sound. (This is also the exact command
`INSTALL.md`'s troubleshooting table uses to diagnose a failed connection.)

**c. Pick up the change in Claude Code**

Restart your Claude Code session (or run `/reload-plugins`). Claude Code owns the process
lifecycle for `ahq-mcp-server-dev` — it re-imports your latest code on every restart, so there
is no separate "start the server" step for normal iteration.

**d. Exercise the changed tool for real**

Ask Claude something that routes to the tool you changed (e.g. "list my AHQ websites") and
confirm real data comes back.

## 5. Running the server standalone (optional)

Useful if you want to confirm the process boots outside of Claude Code, or you're debugging
startup itself.

**Stdio mode** (what Claude Code actually launches) — it will sit waiting on stdin; `Ctrl+C` to
stop:

```powershell
uv run python -m src.mcp_server
```

**HTTP/hosted mode** (only relevant if you're touching `src/http_server.py` / OAuth code) —
starts a real `uvicorn` server on `localhost:8000`:

```powershell
$env:AHQ_MCP_AUTH_SECRET = "any-dev-value"
uv run python -m src.http_server
```

## 6. Dev loop, end to end

```
edit code → uv run pytest → restart Claude Code session → try the tool for real → repeat
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `/mcp` shows `ahq-mcp-server-dev` **failed** | `uv`/Python not on PATH, or you ran `claude mcp add` from the wrong directory. Re-run the smoke check in step 4b from inside the repo. |
| Tool errors say `ahq-mcp-server is not configured: ... is empty` | `.env` is missing, in the wrong folder, or missing a value — the error names the variable and expected path. |
| Tool errors say `Got the web frontend's HTML instead of an API response` | Token predates the `urlDetails` claim — add `AHQ_BASE_URL` to `.env`, pointed at the **API gateway** (e.g. `https://api-dev.automationhq.ai`), never the web UI. |
| Every AHQ call returns 401 | Wrong/expired token in `.env`. A raw browser-session JWT does not work — needs an Organization or User API token. |
| Changes don't seem to take effect | You edited code but didn't restart the Claude Code session — it doesn't hot-reload. |

## See also

- [`INSTALL.md`](INSTALL.md) — end-user install guide (plugin install, not a dev checkout)
- [`DEPLOYMENT.md`](DEPLOYMENT.md) — all three ways to register the server (plugin / plain MCP / hosted HTTP)
- [`CLAUDE.md`](CLAUDE.md) — full platform contract, API gotchas, and architecture notes
- [`evals/README.md`](evals/README.md) — golden-task suite that hits the live dev API end-to-end
