# AHQ MCP Server — Project Context

## What This Is
A Python MCP server that wraps the Aviso-UTAP (AutomationHQ) test automation platform APIs.
Claude speaks plain language; the MCP server translates that into AHQ REST calls.
No AHQ web UI needed — everything happens through MCP tools.

## Authentication
- Header: `X-API-AUTH-KEY: <token>` on every AHQ request (NOT `Authorization: Bearer`)
- Gateway URL: `https://api-dev.automationhq.ai` (NOT `https://dev.automationhq.ai`)
- Org token type: `ORGANIZATION` — signed with a different secret than user JWTs
- `.env` must never be committed

## AHQ Platform Knowledge (Aviso-UTAP)

### Module Map — where things live in the UI

| Module | Navigation Path |
|---|---|
| Test Scripts | Test Management → Test Scripts |
| AI Test Builder | Test Management → AI Test Builder |
| Recorded Scripts | Test Management → Recorded Scripts |
| Pull Requests | Test Management → Pull Requests |
| TestBots | Test Execution → TestBots |
| TestBot Folders | Test Execution → TestBots → Folder View |
| Execution Queue | Administration → Execution Queue |
| Scheduler Admin | Administration → Scheduler Admin |
| Integrations | Administration → Integrations |
| Tunnel | Administration → Tunnel |
| System Status | Administration → System Status |
| Archive Manager | Administration → Archive |
| Project Roles | Administration → Global Settings → Project Roles |
| UI Components (Websites/Pages) | UI Components |

### Test Script Hierarchy
Epics → Stories → Test Scripts (storyId links a script to a story)
A script with `storyId: null` is standalone — visible in "All Test Scripts" flat list, not in any epic/story view.

### Key Terminology
- **TestBot** — an execution configuration that runs a set of test scripts
- **Test Script** — a sequence of test steps (stored as `testSteps[]` in the API, field `name`)
- **Epic** — top-level grouping (e.g. a feature or module)
- **Story** — child of an epic (e.g. a user story or scenario)
- **Suite** — a flat collection of test scripts for batch execution
- **Environment** — execution target (URL + browser config); supplies `gridUrlForExecution` and `browser`
- **Website** — an application under test; fields: `name`, `websiteUrl`
- **Page** — a screen/view within a website; fields: `pageName`, `pageUrl`
- **Locator** — a UI element selector (XPath, CSS, aria-label) attached to a page
- **Recorded Script** — a browser session captured by the TestBot Recorder Chrome Extension
- **Tunnel** — secure bridge that exposes a private/local app to the cloud execution grid

### Project Roles & Permissions
Five permissions: VIEW (blue), EXECUTE (green), EDIT (orange), DELETE (red), SHARE (purple)
VIEW is independent — it is NOT automatically granted when other permissions are added.
Roles: Site Admin, Project Admin, QA Manager, QA Director, Tester, Business Sponsor

### AI Test Builder
Chat-based interface. Three quick-start modes:
- **Test Script from App** — generates steps from an existing UI Components website
- **Test Script from Repo** — generates from a connected source code repository
- **Test Script from Req** — generates from a requirements doc or plain-text description

### Integrations Available
Azure DevOps, Jira, Slack, Jenkins, GitLab, Bitbucket

### Tunnel Commands
`status`, `start`, `stop`, `restart`, `health`, `info`, `logs`, `version`

### Execution Queue — Status Values
`PROCESSING` (running), `ENQUEUED` (waiting), `PENDING` (scheduled)

### Version Control Concepts
- Branches per script (fork from `main`)
- Pull Request lifecycle: Open → Review → Merge (or Close / Resolve Conflicts)
- Conflict resolution: Accept Ours / Accept Theirs / Keep Both (per field and per step)
- Closing a PR does NOT delete the source branch

### Archive / Soft Delete
Deleted assets go to Administration → Archive. Can be restored or permanently deleted.
Asset types: Epics, Stories, Applications, Pages, Locators, Recorded Scripts, Test Scripts, Test Sets, TestBots, TestBot Folders

### Scheduler Admin
Centralized view of all scheduled TestBot runs. Schedules are created per-TestBot (clock icon) and managed here. Toggle Enabled without deleting to pause.

### System Status
Health check per microservice: Liveness, Readiness, Ping — each shows UP (green) or DOWN (red).

---

## API Field Reference (avoid wrong field names)

| Entity | Correct fields |
|---|---|
| Page | `pageName`, `pageUrl` |
| TestScript | `name`, `testSteps` (NOT `steps`) |
| Website | `name`, `websiteUrl` |
| TestBot execution | `gridUrlForExecution`, `browser`, `profileId` |

## MCP Tool Quick Reference

| Tool | When to use |
|---|---|
| `get_ahq_context` | Always call first — loads project snapshot |
| `crawl_url` | Discover pages + locators from a live URL |
| `create_website` / `create_page` / `add_locators` | Build UI component library |
| `create_test_script` | Add a new test script (pass `storyId` to attach to a story) |
| `list_bots` / `execute_bot` | Run a TestBot by name |
| `get_execution_report` | View pass/fail results |
| `schedule_bot_recurring` | Set up a cron schedule |
| `get_service_spec` / `call_api` | Discover and call any AHQ endpoint not covered by a hand-written tool |
