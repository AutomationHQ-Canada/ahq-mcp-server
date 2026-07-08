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

### TestStep shape — never fabricate a `templateId`

A `TestStep` is NOT `{action_type, locator, value}`. Real shape (from `ahq-data-commons`
`TestStep`/`Params`/`TypeValuePair`/`UILocator`):

```
{
  "templateId": "<real id from list_step_templates/search_step_templates>",
  "testStepTitle": "Enter username",
  "sequence": 0,
  "params": {
    "uiLocator": {"locateBy": "xpath", "locatorValue": "//input[@id='username']", "locatorType": "input"},
    "text": {"value": "testuser@example.com"},
    "expected": {"value": "Welcome back"}
  }
}
```

- `templateId` references a live, per-project catalog (platform built-ins + org-defined
  "Common Functions") — there is no fixed enum of action types to hardcode. Always resolve it via
  `search_step_templates`/`list_step_templates` first; use `get_step_template` to see exactly which
  `params` sub-fields a given template expects before filling them in.
- `params.uiLocator` targets an element (click/type/assert-element steps); `params.text.value` holds
  input values (also URLs for navigate steps); `params.expected.value` holds the expected value for
  assertions; `params.variable` references a runtime variable. Only set the sub-fields the chosen
  template actually uses — leave the rest out.
- `locatorValue` may contain `{{placeholder}}` tokens resolved at runtime via `params.locatorParams`
  (index-aligned with `uiLocator.locatorParamNames`) — only needed for dynamic locators.

## Gateway routing gotcha — mtaf-* services

The gateway routes the `managed-testing-*`/`mtaf-cdct-core` family on SHORT route ids, not the repo
name. `src/config/ahq_services.py` constants already reflect this (fixed 2026-07-08) — don't
"correct" them back to the repo name if it looks wrong at a glance:

| Repo name | Real gateway route |
|---|---|
| `managed-testing-service-core` | `/mtaf-core` |
| `managed-testing-virtualization-client` | `/mtaf-sv-client` |
| `managed-testing-virtualization-server` | `/mtaf-sv-server` |
| `mtaf-cdct-core` | `/mtaf-cdct` |

`test-local-execution-services` has NO gateway route at all — it runs on the user's own machine
(ports ~9200/9202), not in the cluster. Any tool targeting it needs a direct-to-localhost call with
a fast-fail liveness check (see `local_exec_client.get_agent_status()`), not a gateway call.

## Services intentionally NOT covered by hand-written tools

These are infra/session plumbing, not something a user would ask for in plain language — don't
treat their absence as a gap to "rediscover":
- `ahq-gateway-services` — pure ingress/auth/tunnel infra
- `ahq-auth-services` — login/SSO/JWT issuance (service-to-service, not conversational)
- Most of `ahq-standalone-local-v2-services` — internal proxy/cache layer for the local agent
  (exceptions: `FakeDataController.generate` and token validation have standalone user-facing value)
- Ops-only endpoints in any service: job queues, log-migration/cleanup/admin endpoints, SSE log streams

## API / Performance Testing (mtaf-core) — a separate flow from UI test scripts

`ahq-test-management-services`' TestBots run UI test scripts (browser automation). `mtaf-core`
(`managed-testing-service-core`) is a completely separate product surface for REST/GraphQL request
testing, chained-workflow testing, and JMeter-backed load testing. Don't conflate the two — a user
asking to "test my API" or "run a load test" means the mtaf-core tools below, not `create_test_script`.

- `list_api_collections` / `get_api_collection` / `create_api_collection` — Postman-style groupings
- `list_api_requests` / `get_api_request` / `create_api_request` / `test_api_request` — individual
  REST/GraphQL requests; `test_api_request` runs one immediately without saving it first
- `import_curl` / `import_postman_collection` — bulk-import existing requests instead of hand-building them
- `list_workflows` / `get_workflow` / `create_workflow` / `test_workflow` — chained multi-request flows
  (e.g. a full user journey); `test_workflow` runs a one-off test without saving
- `list_performance_bots` / `get_performance_bot` / `run_performance_bot` / `stop_performance_bot` /
  `get_performance_results` — JMeter load tests; `run_performance_bot` returns immediately with a
  metrics ID, poll `get_performance_results` for progress (test can run for hours)
- `list_vault_secrets` — metadata only (names/keys); deliberately does NOT expose the
  `/resolve/{key}` endpoint that returns decrypted plaintext, to keep secrets out of the conversation
  transcript by default

## Other niche tool groups (2026-07-08)

- **Local execution agent** (`test-local-execution-services`, runs on the user's own machine, no
  gateway route): `check_local_agent_status` (hits `TestExecutorController`'s `/ping` directly on
  localhost:9202 — NOT `/rest/api/agent/status`, which doesn't exist), `list_local_agents` (via
  `ahq-standalone-local-v2-services`' real path `/rest/api/local/agent/getAllAgents` — note the
  `orgId` header here, no hyphen, unlike every other service's `org-id`)
- **Fake/synthetic test data**: `list_fake_data_types` / `generate_fake_data` (also
  `ahq-standalone-local-v2-services`)
- **Email**: `send_email` (`ahq-email-v2-services`)
- **Pact contract testing** (`mtaf-cdct-core`, niche): `list_consumers`/`create_consumer`,
  `list_providers`/`create_provider`, `list_contracts`/`create_contract`, `run_pact_tests`. Uses
  lowercase `organizationid`/`projectid` headers — a THIRD header-naming convention alongside
  `org-id`/`projectId` (most services) and `orgId` (standalone-local).
- **Service virtualization / API mocking** (`mtaf-sv-server` only, not the near-duplicate
  `mtaf-sv-client`): `list_mock_mappings`, `get_mock_mapping`, `get_mock_mapping_template`,
  `create_mock_mapping`, `delete_mock_mapping`. The mapping body is a raw JSON string, not a typed
  object — sent as `text/plain` like `import_curl`, not `application/json`.

## MCP Tool Quick Reference

| Tool | When to use |
|---|---|
| `get_ahq_context` | Always call first — loads project snapshot |
| `crawl_url` | Discover pages + locators from a live URL |
| `create_website` / `create_page` / `add_locators` | Build UI component library |
| `search_step_templates` / `list_step_templates` / `get_step_template` | Resolve a real `templateId` before writing any test step |
| `create_test_script` | Add a new test script (pass `storyId` to attach to a story) |
| `list_bots` / `execute_bot` | Run a TestBot by name |
| `get_execution_report` | View pass/fail results |
| `schedule_bot_recurring` | Set up a cron schedule |
| `test_api_request` / `test_workflow` / `run_performance_bot` | API/load testing — see mtaf-core section above |
| `get_service_spec` / `call_api` | Discover and call any AHQ endpoint not covered by a hand-written tool |
