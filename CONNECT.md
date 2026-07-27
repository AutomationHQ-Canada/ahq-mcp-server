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

## Microsoft Copilot Studio (and Microsoft 365 Copilot agents)

Copilot Studio reaches MCP servers through Power Platform's connector infrastructure, so this is
a different path from VS Code's Copilot Chat above (that one is the plain MCP client and is
covered by the section before this).

1. In Copilot Studio, open your agent's **Tools** page → **Add a tool** → **New tool** →
   **Model Context Protocol**.
2. Fill in **Server name**, **Server description** (the agent's orchestrator uses this to decide
   when to call AHQ — describe it as test automation: scripts, bots, execution reports), and the
   **Server URL** above.
3. For authentication choose **OAuth 2.0** → **Dynamic discovery**. The server supports dynamic
   client registration with discovery, so there is no client ID/secret to create.
4. Select **Create**, then **Add to agent** and create a new connection. You'll be sent to the
   same AutomationHQ consent page — paste your ORGANIZATION token, pick a project, **Authorize**.

> **Use OAuth, not API key.** Copilot Studio's API-key auth can only send a single header, but
> header-based auth here needs two (`X-API-AUTH-KEY` *and* `projectId`). OAuth avoids this
> entirely — the consent page picks the project. If you do try API key, the server now returns a
> clear error naming the missing `projectId` rather than silently answering with empty results.

Copilot Studio supports only the Streamable HTTP transport (SSE was dropped in August 2025),
which is what this server speaks. Access is governed by Power Platform data policies — if a DLP
policy restricts connectors, it restricts this MCP server's tools too.

## Microsoft 365 Copilot chat (declarative agent)

To get AHQ tools inside M365 Copilot chat (m365.cloud.microsoft/chat), someone builds a
**declarative agent** that wraps this server, then publishes it to the tenant. This is a build
step, not a connect-a-URL step — see `DEPLOYMENT.md` for the server side.

In Visual Studio Code with the **Microsoft 365 Agents Toolkit** (6.12.0+):

1. **Create a New Agent/App** → **Declarative Agent** → **Add an Action** → **Start with an
   MCP Server**.
2. Enter the server URL above.
3. Authentication type: **OAuth (with dynamic registration)** — this server supports DCR, so
   there is no client ID or secret to create. The toolkit writes the registration into the
   agent's plugin manifest for you.
4. **Provision** from the Lifecycle pane (needs *Custom App Upload Enabled* and *Copilot Access
   Enabled* on the M365 account — ask the tenant admin if either is missing).
5. Open `https://m365.cloud.microsoft/chat`, find the agent in the **Agents** sidebar, and sign
   in when prompted — the same AutomationHQ consent page appears.

> **Pin a curated tool set.** This server exposes 130+ tools; a declarative agent's orchestrator
> chooses from tool descriptions alone, so pin the dozen or so the agent actually needs rather
> than taking all of them via dynamic discovery. Keep destructive tools
> (`permanently_delete_asset`, `merge_pull_request`) out of an agent aimed at general users.

Note that M365 Copilot **federated connectors** are a *different* feature with a read-only tool
restriction — declarative agents have no such limit, which is why this is the recommended path.

## Lovable (custom MCP chat connector)

Lovable reaches MCP servers as "chat connectors" — the tools are available to Lovable's AI while
it builds for you, and are deliberately never part of the app it publishes. If you want a
Lovable-built app to call AHQ at runtime, that's an ordinary API integration in the generated
code, not this.

1. **Connectors** dashboard → scroll to the bottom → the **Custom MCP** card.
2. Name the server (e.g. `AutomationHQ`) and enter the server URL above.
3. Leave the authentication method as **OAuth** (Lovable's default).
4. **Add & authorize** → the AutomationHQ consent page opens — paste your ORGANIZATION token,
   pick a project, **Authorize**.

> **Don't use the bearer-token/API-key option.** `Authorization: Bearer` here means this server's
> own encrypted session blob, not an AHQ token, so a pasted org token fails to decode; and the
> header path needs `X-API-AUTH-KEY` *and* `projectId`, which that option can't send. OAuth is
> the only route that works.

Lovable's fixed callback (`https://api.lovable.dev/workspaces/connectors/mcp/oauth/callback`) is
allowlisted from v1.6.7 onward — an earlier server refuses registration with `invalid_redirect_uri`.

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
| Copilot Studio: tools return empty lists ("you have no websites") | You connected with **API key** auth, which can only send one header, so `projectId` never arrives. Reconnect using **OAuth 2.0 → Dynamic discovery** instead. |
| Copilot Studio: adding the server fails on the redirect/callback URL | Power Platform's per-connector callback (`https://<region>.consent.azure-apim.net/redirect/...`) is allowed from v1.6.4 onward — make sure the server you're hitting is running that version or later. |

## For developers

Server-side OAuth/consent implementation details (stateless token design, redirect-URI policy,
per-client quirks found live) are documented in [`CLAUDE.md`](CLAUDE.md) under "Hosted mode
authentication". Deployment/env-var reference is in [`DEPLOYMENT.md`](DEPLOYMENT.md) (Option C).
