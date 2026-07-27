# Connecting to the AutomationHQ MCP server

Use AutomationHQ's test-automation tools directly from your AI assistant — generate test scripts,
run TestBots, read execution reports, manage branches and pull requests — by connecting one URL.
Nothing to install.

Works with **Claude Desktop, claude.ai, VS Code (GitHub Copilot Chat), Microsoft Copilot Studio,
Microsoft 365 Copilot, Lovable, Cursor and Windsurf**.

> Using **Claude Code**? Install the plugin instead — see [`INSTALL.md`](INSTALL.md). It adds 9
> guided workflow skills and can drive a test agent running on your own machine, which a URL
> connection cannot.

---

## Before you start

**1. Your server URL**

```
https://api-dev.automationhq.ai/ahq-mcp-server/mcp
```

> **Pilot environment.** If AutomationHQ has given you a different URL for your organization,
> use that one instead — every instruction below is otherwise identical.

**2. An AutomationHQ ORGANIZATION API token**

AHQ web app → **Administration → Settings → API Tokens → Create**, type **Organization**.

A personal/user token will not work — the consent page rejects it. Ask your AHQ administrator if
you can't create one yourself.

You'll paste this token into a browser page once per client, never into a config file.

---

## How connecting works

The same four steps in every client:

1. You add the server URL to your AI client.
2. The client opens your browser to AutomationHQ's sign-in page.
3. You paste your Organization token and pick a project (skipped if your org has only one).
4. The browser returns you to the client, now showing **Connected**.

Your token is validated live against AutomationHQ each time you connect. The client only ever
stores an encrypted session token, never the token itself in plaintext.

---

## Claude Desktop and claude.ai

1. **Settings → Connectors**
2. **Add custom connector**
3. Name it (e.g. `AutomationHQ`) and paste the server URL
4. **Add**, then **Connect** on the new card
5. Paste your Organization token on the consent page, choose a project, **Authorize**
6. Return to Claude — the connector shows **Connected**

Start a **new** chat and ask *"list my AHQ websites"* to confirm. An existing conversation won't
pick up a newly added connector.

## VS Code + GitHub Copilot Chat

Needs the **GitHub Copilot Chat** extension and an active Copilot subscription. VS Code must be
in a **trusted workspace** — in Restricted Mode, MCP servers don't start.

1. `Ctrl+Shift+P` / `Cmd+Shift+P` → **MCP: Add Server...**
2. **HTTP (HTTP or Server-Sent Events)**
3. Paste the server URL
4. Name it (e.g. `AHQ-MCP`)
5. **Global** scope, unless you want it in one workspace only
6. Paste your Organization token on the consent page, pick a project, **Authorize**
7. Open Copilot Chat, switch the mode dropdown to **Agent**, click the tools icon (🔧) to confirm
   the AHQ tools are listed

Step 7 catches most "it isn't working" reports — **MCP tools only appear in Agent mode**, not Ask
or Edit.

> Copilot Chat sometimes prefers its own built-in tools (git, terminal, file search) for an
> ambiguous request. If something that clearly needs AHQ data comes back empty, name it
> explicitly: *"using the AHQ tools, list my test scripts"*. That's Copilot's tool-selection
> behaviour, not a broken connection.

## Microsoft Copilot Studio

Copilot Studio reaches MCP servers through Power Platform's connector infrastructure — a
different path from VS Code's Copilot Chat above, despite the shared name.

**Prerequisites** (all tenant-level, your M365 admin may need to arrange them):

- A Power Platform environment **with Dataverse** — without Dataverse the environment won't
  appear in Copilot Studio at all
- A Copilot Studio licence, or self-service trials enabled
- A DLP policy that permits custom connectors, if your tenant has one

**Steps**

1. Your agent → **Tools** → **Add a tool** → **New tool** → **Model Context Protocol**
2. **Server name**: `AutomationHQ`
3. **Server description** — this is the only text the agent's orchestrator uses to decide when to
   call AutomationHQ, so make it specific:
   > AutomationHQ test automation platform. Create and run UI test scripts and TestBots, inspect
   > execution reports and pass/fail results per step, manage test suites, environments, branches
   > and pull requests, and query websites, pages and UI locators.
4. **Server URL**: as above
5. **Authentication**: **OAuth 2.0** → **Dynamic discovery** — no client ID or secret to create
6. **Create** → **Add to agent** → **Create new connection** → consent page → **Authorize**

> **Use OAuth, not API key.** Copilot Studio's API-key auth sends a single header, but header
> authentication here needs two. With only one, AutomationHQ returns an empty result set rather
> than an error — so your agent would report "you have no test scripts" instead of failing
> visibly. OAuth avoids this entirely; the consent page selects the project.

Copilot Studio supports only the Streamable HTTP transport, which is what this server speaks.

## Microsoft 365 Copilot (declarative agent)

Getting AHQ tools into M365 Copilot chat means building a **declarative agent** — a build step,
not a connect-a-URL step.

In VS Code with the **Microsoft 365 Agents Toolkit** (6.12.0+):

1. **Create a New Agent/App** → **Declarative Agent** → **Add an Action** → **Start with an MCP
   Server**
2. Enter the server URL
3. Authentication: **OAuth (with dynamic registration)** — no client ID or secret needed; the
   toolkit writes the registration into the agent's manifest
4. **Provision** from the Lifecycle pane (needs *Custom App Upload Enabled* and *Copilot Access
   Enabled* — ask your tenant admin)
5. Open `m365.cloud.microsoft/chat`, find the agent in the **Agents** sidebar, sign in

> M365 Copilot **federated connectors** are a different feature with a read-only tool
> restriction. Declarative agents have no such limit, which is why this is the recommended path.

## Lovable

Lovable connects MCP servers as **chat connectors** — the tools are available to Lovable's AI
while it builds for you. They are deliberately never part of the app Lovable publishes, so this
does not let a Lovable-built app call AutomationHQ at runtime; that would be an ordinary API
integration in the generated code.

1. **Connectors** dashboard → scroll to the bottom → **Custom MCP**
2. Name it (e.g. `AutomationHQ`) and enter the server URL
3. Leave authentication as **OAuth** (the default)
4. **Add & authorize** → consent page → paste token, pick project, **Authorize**

> Don't use the bearer-token/API-key option — it can't carry everything this server's header
> authentication needs. OAuth is the only route that works.

## Cursor / Windsurf

Both follow the same MCP OAuth specification as VS Code and Claude Desktop, so the same pattern
applies: add the server URL as an HTTP/remote MCP server in the client's MCP settings and follow
the browser consent prompt.

If your version doesn't support OAuth, there's a header-based fallback. It skips the browser
step, but you manage the token yourself and it never rotates automatically:

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

Both headers are required — with only the token, AutomationHQ answers with an empty result set
rather than an error. Find the project UUID in the AHQ web app's URL
(`.../<orgId>/<projectId>/...` — the **second** UUID).

Cursor: `.cursor/mcp.json` in your project, or `~/.cursor/mcp.json` globally. Windsurf: its own
`mcp_config.json`, same shape.

---

## Please read before storing credentials in a test script

**Passwords used in test steps appear in plaintext in execution reports.**

AutomationHQ's secret vault keeps a credential out of the stored test script — the step displays
as `Enter [vault: my_password] for "Password field"` and the real value appears nowhere in the
script document. That part works as expected.

However, when the test runs, the executor resolves the secret and writes the **resolved value**
into the execution report:

```
"statusMessage": "Entered value MyRealPassword123"
```

So anyone who can read an execution report can read that credential. The vault protects storage,
not the full lifecycle.

**What to do:** use dedicated test accounts with credentials you're willing to have visible in
report history, and never reuse a production or personal password in a test script. Raise this
with your AutomationHQ contact if report-level protection matters for your use case.

---

## What a URL connection can't do

| Limitation | Why |
|---|---|
| Running tests on a **test agent on your own machine** | The hosted server can't reach your local machine — there's no reverse channel. Use a cloud grid, or the Claude Code plugin ([`INSTALL.md`](INSTALL.md)) for local runs. |
| Reading files from your computer | The hosted server has no access to your filesystem. The plugin does. |
| Copilot Studio under a restrictive DLP policy | Power Platform data policies govern this like any connector. |

## Choosing which tools to enable

This server exposes **136 tools**. Clients that let you pick (Copilot Studio, M365 declarative
agents) will choose badly from all of them at once — an orchestrator selects on tool descriptions
alone. Enable the dozen or so your agent actually needs.

A reasonable starting set:

```
get_ahq_context        list_test_scripts     get_test_script
list_bots              execute_bot           get_execution_status
get_execution_report   list_recent_runs      list_websites
list_environments      list_suites           list_branches
```

Keep destructive tools — `permanently_delete_asset`, `merge_pull_request`, `delete_test_script` —
out of any agent aimed at general users.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Consent page says the token "doesn't look like an ORGANIZATION token" | You pasted a personal/user token. Create an **Organization**-type token in Administration → API Tokens. |
| Consent page says AutomationHQ "rejected this token" | The token is expired or deleted. Create a fresh one. |
| "This connection link has expired" | The browser tab sat open more than 10 minutes, or the link was reused. Start the connection again from your client. |
| Connected, but every list comes back empty | You're connected to a project with no data, or you used header authentication without `projectId`. Reconnect with OAuth, or check the project you selected. |
| Connected, but no tools appear | VS Code: confirm Copilot Chat is in **Agent** mode. Claude Desktop: start a **new** chat. |
| A tool fails saying it needs a local agent | That action requires a test agent on your own machine, which a URL connection can't reach. Use the Claude Code plugin, or point the bot at a cloud grid. |
| Registration or callback URL is rejected | Your client's OAuth callback isn't recognised by the server yet. Send the exact error to your AutomationHQ contact — it names the URL, and allowlisting it is a quick configuration change. |
| Anything else | Contact your AutomationHQ representative with the exact error text. |

---

## For developers

Server-side OAuth/consent implementation details are in [`CLAUDE.md`](CLAUDE.md) under "Hosted
mode authentication". Deployment and environment-variable reference is in
[`DEPLOYMENT.md`](DEPLOYMENT.md) (Option C).
