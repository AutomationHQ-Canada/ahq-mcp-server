# Connecting to the hosted AHQ MCP server (no install required)

This is for anyone who wants to use AHQ's MCP tools from **Claude Desktop, claude.ai,
VS Code (GitHub Copilot Chat), Cursor, or Windsurf** without installing anything — the server
runs centrally and you connect with just a URL. (If you use **Claude Code** instead, install the
plugin per [`INSTALL.md`](INSTALL.md) — it's a different, richer setup with 8 workflow skills.)

**Server URL (dev):** `https://api-dev.automationhq.ai/ahq-mcp-server/mcp`

**What you need first:** an AHQ **ORGANIZATION** API token — AHQ web app → Administration →
Settings → API Tokens → Create (type: **Organization**, not a personal user token). Ask your
admin if you can't create one yourself. Keep it somewhere safe; you'll paste it into a browser
consent screen once per client, not into the MCP client's config.

---

## How the connection works (same for every OAuth-capable client)

1. You add the server URL above to your MCP client.
2. The client opens your browser to AutomationHQ's sign-in page for MCP.
3. You paste your ORGANIZATION token and pick a project (skipped automatically if your org only
   has one project).
4. Your browser redirects back to the client, which now shows the connection as **connected**.

Nothing is stored in plaintext on your machine — the client only ever holds an encrypted session
token, and the org token you paste is validated live against AHQ every time you connect.

---

## Claude Desktop (confirmed working, 2026-07-16)

1. Open Claude Desktop → **Settings → Connectors**.
2. Click **Add custom connector**.
3. Name: `AutomationHQ` (anything you like). URL: the server URL above.
4. Click **Add**, then **Connect** on the new connector's card.
5. A browser tab opens AutomationHQ's consent page. Paste your ORGANIZATION token, choose a
   project if asked, and click **Authorize**.
6. The browser tab shows a success message — go back to Claude Desktop. The connector now shows
   **Connected**. Start a new chat and ask something like *"list my AHQ websites"* to confirm.

**Claude.ai (web)** uses the identical Connectors flow — Settings → Connectors → Add custom
connector — same steps as above.

## VS Code + GitHub Copilot Chat (confirmed working, 2026-07-16)

Requires the **GitHub Copilot Chat** extension and an active Copilot subscription. VS Code must
be in a **trusted workspace** — if it's in Restricted Mode, MCP servers won't start; click
"Manage Workspace Trust" and trust the folder first.

1. Open the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`) → run **MCP: Add Server...**.
2. Choose **HTTP (HTTP or Server-Sent Events)**.
3. Paste the server URL above.
4. Give it a name (e.g. `AHQ-MCP`).
5. Choose **Global** (available in every workspace) unless you specifically want it scoped to
   one project.
6. VS Code opens your browser to the same AutomationHQ consent page — paste your ORGANIZATION
   token, pick a project if asked, and **Authorize**.
7. Back in VS Code, open Copilot Chat, switch the mode dropdown to **Agent**, and click the
   tools icon (🔧) to confirm the AHQ tools are listed and enabled.

> Note: GitHub Copilot Chat sometimes prefers its own built-in tools (git, terminal, file search)
> over an MCP tool for an ambiguous request even when connected correctly. If a request that
> clearly needs AHQ data comes back empty or wrong, try naming the tool or being explicit
> ("using the AHQ MCP tools, list my test scripts") — this is Copilot's own tool-selection
> behavior, not a sign the connection is broken.

## Cursor / Windsurf

Not yet live-validated against this server (as of 2026-07-17), but both follow the same MCP
OAuth spec as VS Code/Claude Desktop, so the same pattern should work: add the server URL as an
HTTP/remote MCP server in the client's MCP settings and follow the browser consent prompt.
If OAuth doesn't work in your version, use the header-based fallback instead (no browser step,
but you manage the token yourself and it never expires/rotates automatically):

```json
{
  "mcpServers": {
    "ahq": {
      "url": "https://api-dev.automationhq.ai/ahq-mcp-server/mcp",
      "headers": {
        "X-API-AUTH-KEY": "<your ORGANIZATION token>",
        "projectId": "<the project's UUID>"
      }
    }
  }
}
```

(Cursor: `.cursor/mcp.json` in your project, or the global `~/.cursor/mcp.json`. Windsurf: its
own `mcp_config.json` in the same shape.) Find the project UUID in the AHQ web app's URL:
`dev.automationhq.ai/<orgId>/<projectId>/...` — the second UUID.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Consent page says the token "doesn't look like an ORGANIZATION token" | You pasted a personal/user JWT. Create an **Organization**-type token in Administration → API Tokens instead. |
| Consent page says AutomationHQ "rejected this token" | Token is expired or deleted — check Administration → API Tokens and create a fresh one. |
| Project list is empty or wrong after connecting | Fixed 2026-07-17 — make sure you're on `ahq-mcp-server` v1.3.0+. Earlier versions validated every token against this server's own (dev) gateway, so a prod token showed dev's (wrong) projects. |
| "This connection link has expired" | The browser tab sat open too long (txn expires after 10 minutes) or you reused an old link. Go back to your MCP client and start the connection again. |
| Client shows connected but a tool call fails with a local-agent error | That tool needs your own machine's local agent (`localhost:9202`), which a hosted connector session can't reach — only stdio (the Claude Code plugin) can. Use the plugin for that specific action, or point the bot at a cloud grid instead. |
| VS Code: registration/connection fails with a confusing client-id error | Fixed server-side 2026-07-16 (VS Code's Copilot Chat client skips standard registration) — make sure you're hitting the current dev server; no client-side workaround needed. |
| Everything looks connected but no tools appear | In VS Code, confirm Copilot Chat is in **Agent** mode (not Ask/Edit) — MCP tools only surface there. In Claude Desktop, start a *new* chat after connecting. |

## For developers

Server-side OAuth/consent implementation details (stateless token design, redirect-URI policy,
per-client quirks found live) are documented in [`CLAUDE.md`](CLAUDE.md) under "Hosted mode
authentication". Deployment/env-var reference is in [`DEPLOYMENT.md`](DEPLOYMENT.md) (Option C).
