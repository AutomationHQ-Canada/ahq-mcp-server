# Deploying / Installing ahq-mcp-server

Two ways to use this server with Claude Code. Both give you the same 102 MCP tools; the plugin
additionally installs the curated workflow skills.

## Option A — Claude Code plugin (recommended)

The repo doubles as a Claude Code plugin (`.claude-plugin/plugin.json` + `skills/*/SKILL.md` +
`.mcp.json`). Installing it registers the MCP server AND the 7 workflow skills
(`/ahq-gen-from-url`, `/ahq-gen-from-requirements`, `/ahq-run-bot`, `/ahq-schedule-bot`,
`/ahq-view-report`, `/ahq-view-performance`, `/ahq-dashboard`) in one step — no matter which
directory you're working in.

```
# once the repo is on GitHub:
/plugin marketplace add AutomationHQ-Canada/ahq-mcp-server
/plugin install ahq-skills@automationhq
```

Prerequisites on the machine:
1. Python 3.12+ with this repo's dependencies installed (`pip install .` or `uv sync` from the
   plugin/checkout directory — dependencies are declared in `pyproject.toml`).
2. `playwright install chromium` — one-time browser download for the `crawl_url` tool, and
   again after any playwright version bump (the pip package and browser build must match;
   playwright is pinned to a minor version in `pyproject.toml` for exactly this reason —
   bump the pin and reinstall the browser together). Skippable if you never crawl.
3. A `.env` in the plugin root with `AHQ_BASE_URL` and `AHQ_API_TOKEN` (an ORGANIZATION token
   from Administration → Settings → API Tokens). `.env` is never committed.

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

## Hosted (HTTP) mode

`src/http_server.py` serves the same tools over HTTP for a centrally-hosted deployment;
credentials come per-request from `X-API-AUTH-KEY` / `org-id` / `projectId` headers instead of
`.env`. Some local-machine tools (crawling, local agent checks) are disabled in hosted mode.
The CI workflow (`.github/workflows/ci.yml`) + Helm chart draft (`deploy/argocd-chart-draft/`)
cover cluster deployment — see the chart README for the open DevOps questions.

## Note on `skills/` vs `.claude/skills/`

`skills/<name>/SKILL.md` is the plugin-distribution layout (what `/plugin install` picks up).
`.claude/skills/*.md` is the repo-local layout that works when working inside this repo.
They are the same content — when editing a skill, edit BOTH copies (or edit `.claude/skills/`
and re-copy) until the repo-local copies are retired.
