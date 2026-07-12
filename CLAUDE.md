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
`status`, `start`, `stop`, `execute` — these 4 ONLY. (This list previously also claimed
`restart`/`health`/`info`/`logs`/`version` — those are not implemented anywhere in
`ahq-gateway-services` and never were; corrected 2026-07-12.) Tunnel endpoints are served at the
gateway ROOT (`/tunnel`, `/tunnel-launcher`, no service prefix) and require a `ROLE_TUNNEL_CLIENT`
JWT — the org API token 403s, so `TunnelClient` mints one per call via `POST /token/tunnel` and
sends it as `Authorization: Bearer`.

**Known dev-environment gap (2026-07-12)**: the deployed dev gateway 403s even a freshly-minted
tunnel token (confirmed live, bearer-only). The source's `TunnelTokenController` adds
`ROLE_TUNNEL_CLIENT` to the token's `roles` claim with a `// <-- add this line` comment — the
deployed build evidently predates that fix and mints role-less tokens. The tunnel tools match
current source and will start working when the gateway is redeployed; a tunnel-tool 403 on dev is
this, not a client bug.

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

### TestStep shape — never fabricate a `templateId`, and use `parameters` NOT `params`

A `TestStep` is NOT `{action_type, locator, value}`, and its values do NOT go in the `Params params`
field (that typed field exists on the entity but is NOT what `TestScriptController` reads to build
step titles or execution values — confirmed live, twice, the hard way: a script created with only
`params` set produced literal `"(Pending) typeValuePair not found"`/`"(Pending) uiLocator not found"`
text in every step). The field that actually drives everything is the generic
**`List<Parameters> parameters`**, keyed by the placeholder name in `templateTitle`. Proven-working
shape (this exact payload produced correct, human-readable step titles against a live org):

```json
{
  "templateId": "template-id-3",
  "templateTitle": "Enter {{text}} for the {{ui-locator}}",
  "sequence": 1,
  "parameters": [
    {
      "key": "ui-locator",
      "value": {"locatorId": "2be39546-2861-4e02-92b6-ab8a2ff4c126"},
      "paramClass": "ai.automationhq.commons.entities.assets.UILocator"
    },
    {
      "key": "text",
      "value": {"type": 0, "value": "testuser@example.com"},
      "paramClass": "ai.automationhq.commons.entities.assets.TypeValuePair"
    }
  ]
}
```

- `templateId` references a live, per-project catalog (platform built-ins + org-defined
  "Common Functions") — there is no fixed enum of action types to hardcode. Always resolve it via
  `search_step_templates`/`list_step_templates` first; use `get_step_template` to see exactly which
  placeholder names (`{{...}}` tokens in `templateTitle`) a given template expects.
- **`templateTitle` is REQUIRED for built-in templates** (`templateId` like `"template-id-N"`) —
  copy the exact `templateTitle` string (placeholders intact) from the search/get result verbatim.
  Confirmed via `TestScriptController.updateIdForSteps()` →
  `getTestStepTitleFromTemplateTitleAndParameterList(step.getTemplateTitle(), ...)`: for built-ins
  the server does `templateTitle.contains("{{")` directly on whatever the CALLER sent — it does
  **not** re-fetch the Template document server-side. Omit it and every `create_test_script` call
  with a built-in `templateId` throws a 500 (`Cannot invoke "String.contains(...)" because
  "templateTitle" is null`). Common-Function templateIds (real UUIDs, not `template-id-N`) take a
  different code path (`generateCommonFunctionTitle`) that derives the title itself — `templateTitle`
  is not needed for those.
- **Each `parameters[]` entry's `key` must match a `{{placeholder}}` name in `templateTitle`**
  (e.g. `templateTitle: "Enter {{text}} for the {{ui-locator}}"` needs one entry keyed `"text"` and
  one keyed `"ui-locator"`). Confirmed via `TestScriptController.updatedValueFromParameterList()`'s
  switch statement, keyed on the placeholder name.
- **`ui-locator`/`uiLocator` key**: value is `{"locatorId": "<real id>"}` — just a reference to a
  locator already saved via `add_locators`/`pushSpyElements`. **Do not fabricate `locateBy`/
  `locatorValue`/`locatorType` here** — the server looks the real locator up by `locatorId` on the
  page and enriches those fields itself (`TestScriptController.enrichUILocatorsWithPageId` /
  `enrichUILocatorParameter`). A locatorId that doesn't exist on any page produces
  `"(Pending) uiLocator not found"` in the step title, not an error.
- **Any scalar key** (`text`, `number`, `expected`, ...): value is a `TypeValuePair`:
  `{"type": <int>, "value": "<literal>"}`. `type` codes (from `typeAwareDisplay()`): `0` = literal
  (the common case), `1` = data-driven column, `2` = configuration var, `3` = runtime variable,
  `5` = parameter reference, `6` = faker/random, `7` = vault secret.
- `testStepTitle` is optional — the server regenerates it from `templateTitle` + `parameters` on
  every save/read (`getTestScriptById` does the same rebuild), so don't rely on whatever value you
  send surviving as-is.
- `search_step_templates`'s project-scoped variant (`/rest/api/templates/{projectId}/search`) only
  returns this org's own saved custom templates and is often empty. **Built-in templates only
  surface through the root-level `/rest/api/templates/search?title=` endpoint** (merged with this
  org's Common Functions) — this is what `test_mgmt_client.search_templates()` actually calls.
  Single-word searches work far better than phrases: "Navigate" only matches history back/forward,
  use "Go to"/"Open" for URL navigation; "Enter Text" matches nothing, use "Enter"; "Assert Text"
  matches nothing, this platform's verb is "Verify".

### create_test_script — required fields, now validated before the API call (2026-07-10)

`ahq-data-commons`' `TestScript` entity carries zero Bean Validation annotations — "required" was
never enforced by the entity itself, only by `automationhq-frontend-v2`'s own create-script form
(zod schema). That frontend schema is the real, authoritative contract, confirmed field-by-field
this session, and `src/schema/asset_kinds.py`'s `TestScriptCreateArgs` now enforces the same rules
**before** `create_test_script` reaches the API — a missing field returns a clean `{"error": ...}`
immediately instead of a live 500 or a silently invisible/broken script:

- **`name`** — required, 1-120 characters.
- **`website_id`** — required (was previously only "recommended" here — that was wrong). Separate
  field from `page_id`. Drives the UI's "Application" column; a script with only `page_id` is
  invisible in the Table View.
- **`story_id`** — required (was previously only "recommended" here — that was wrong). A script
  with no story attached is excluded from the Table View's default listing entirely, even though
  the user-guide documents that view as "flat list of all scripts." Get a real one via
  `list_epics` → `list_stories`; if nothing fits, use `create_epic`/`create_story` (both now
  exposed as tools — previously dead code in `test_mgmt_client.py`) rather than skipping the field.
- **`status`** — required, one of: Not Started, In Progress, Ready, To Be Repaired, On Hold.
  Defaults to `"Not Started"` if omitted. Sending it as an unrecognized value is now rejected
  locally instead of tripping the UI editor's `"Expected string, received null"` validation later.
- **`repair_comment`** — required only when `status` is `"To Be Repaired"` (a conditional rule from
  the frontend form, not documented here before this session). Omit otherwise.
- **`type`** (`script_type` param) — plain `String`, no server-side default; Jackson treats an
  absent key the same as JSON `null`, which trips the UI editor's validation on open even though
  creation succeeds. Defaults to `"WEB"` — leave unless there's a real reason to change it.
- Each step's `templateId` referencing a built-in template (`"template-id-N"`) still requires
  `templateTitle` verbatim, exactly as before — now enforced by the same validator instead of only
  documented (search/get_step_template results copy the string; the server does not fetch it for
  built-ins, and omitting it 500s).

Also: **`main` can be a protected branch** — direct `PUT` edits to an existing script on `main` may
403 (`"Direct edits to protected branch 'main' are not allowed. Create a working branch and use a
Pull Request."`). If you need to fix a mistake on a script that's already on `main`, delete and
recreate rather than editing, unless a PR flow is explicitly wanted.

### Version Control tools (2026-07-12)

`ProjectBranchController` (`/rest/api/projects/{projectId}/branches`) + `PullRequestController`
(`/rest/api/projects/{projectId}/pull-requests`), both test-management, standard `org-id` header.
14 tools; full branch→commit→PR→diff→close cycle verified live (PR #16).

- **Branch names travel as QUERY params (`?branchName=`), never path segments** — names may
  contain slashes (`feature/login`).
- **`create_branch` is two-phase**: the server's preflight conflict check may return
  `status: NEEDS_CONFIRMATION` instead of creating. The client/tool surfaces this and never
  auto-retries — relay to the user, resend with `confirmed=true` only after they agree.
  `strategy`: `FROM_BRANCH` (default) or `FROM_CURRENT`. Lombok `boolean isProtected` binds as
  JSON `"protected"` (client sends both spellings).
- **PR lifecycle endpoints (`approve`/`merge`/`close`/`rebase`/`ready-for-review`) take NO
  request body** — do not invent one. Closing a PR does NOT delete the source branch.
- `get_scripts_for_branch` (GET `/branches/scripts?branchName=`) is the ONLY correct answer to
  "which scripts are on branch X" — `TestScript.currentBranchName` does not reflect real
  membership (confirmed live: 1 vs the true 7).
- **Deferred to 9d-ii**: conflict resolution (`/merge/continue` with resolvedSteps /
  keepBothSteps / resolvedFields, PR rebase) — `merge_pull_request` returning a CONFLICTS status
  means "send the user to the UI's Resolve Conflicts flow".

### Project Roles (2026-07-12)

`ProjectRoleController` lives in **`ahq-test-management-services`** (not user-management, despite
being an admin feature), base `/rest/api/projects/{projectId}/roles`, standard `org-id` header.
Tools: `list_project_roles` / `create_project_role` / `update_project_role_permissions` /
`delete_project_role` / `assign_project_role` / `list_project_members`. All verified live except
`assign_project_role` (unit-tested only — assigning would change a real user's access).

- Permissions are exactly the 5-value enum `VIEW`/`EXECUTE`/`EDIT`/`DELETE`/`SHARE` (validated
  locally). **VIEW is independent — never add it implicitly** when granting others.
- **Role name is immutable** — the update endpoint reads only `permissions`; there is
  deliberately no rename parameter on the tool. Rename = create new + delete old.
- System roles (SITE_ADMIN, TESTER, PROJECT_ADMIN, QA_MANAGER, QA_DIRECTOR) cannot be deleted.
- `CreateRoleRequest.isDefault` is a Lombok `boolean isDefault` — Jackson's property name is
  `"default"`, not `"isDefault"`; the client sends both spellings so the flag actually binds.

### Archive Manager (2026-07-12)

One generic tool set — `list_archived_assets` / `restore_asset` / `permanently_delete_asset` —
covers 10 entity types via an `entity_type` enum (epic, story, website, page, locator,
test_script, test_suite, test_bot, test_bot_folder, recorded_script). All verified live.

- All `*ArchiveController`s live in **`ahq-user-management-services`** (base path `/api/...`,
  NOT `/rest/api/...`), extending one generic `ArchiveController<T, ID>`:
  `GET {prefix}/archived`, `POST {prefix}/{id}/archive|restore`, `DELETE {prefix}/{id}/permanent`.
  The archived-list endpoint reads the **`organizationId`** header (third controller family found
  using that spelling instead of `org-id`).
- **Two route deviants**, handled inside the clients: `locator` lists at the prefix ROOT
  (`GET /api/archived-locators`, no `/archived` suffix) and hard-deletes at `DELETE /{id}` (no
  `/permanent`); `recorded_script`'s archive endpoints live on `RecordedScriptController` in
  **test-management** (`/rest/api/recorded-scripts/archived`, pages with `offset` not `page`) —
  the dispatcher routes that entity to `TestMgmtClient`.
- There is no archive *action* tool: archiving IS each module's own DELETE (soft-delete). E.g.
  `DELETE /rest/api/epics/{id}` archives the epic (and cascades stories/scripts).
- `permanently_delete_asset` is irreversible and only works on already-archived assets — confirm
  with the user first.

### Recorded Scripts (2026-07-12)

Recordings are created by the TestBot Recorder Chrome Extension, not by tools — the MCP surface is
read + promote: `list_recorded_scripts` / `get_recorded_script` / `promote_recorded_script`.

- **Header inconsistency INSIDE one service**: `RecordedScriptController` reads
  `@RequestHeader("organizationId")`, while every other controller in the same
  `ahq-test-management-services` (TestScript, Epic, TestBot, ...) reads `org-id`. The client adds
  `organizationId` per recorded-script call via `_recorded_headers()` — don't "simplify" it away.
- **`story_id` is required for a first-time promotion** — the server itself throws
  (`"storyId is required for first-time promotion"`), and it travels as a **query param**
  (`?storyId=...`), not in the body. Re-promoting an already-promoted recording updates the linked
  TestScript and ignores storyId. `get_recorded_script` returns `promotedTestScriptId` to tell the
  two cases apart.
- The promote body (`PromoteRecordedScript`) is all-optional overrides (name/websiteId/status/
  description/steps/keepStepIds/...) — but `currentBranchName` is always sent explicitly
  (default `"main"`) for the same reason `create_test_script` does: a blank branch falls back to
  the API token's ambient checked-out-branch ProjectState, which is not reliably `main`.

### Common Function (User Test Step) CRUD — the destructive-PUT trap (2026-07-12)

`PUT /rest/api/commonFunctions/{id}` is a **full-document replace, not a patch**:
`CommonFunctionController.updateCommonFunction` saves the request body directly, forcing only
`commonFunctionId` back onto it — it does NOT carry over `testSteps`, `parameters`, `returnType`,
`websiteId`, `status`, or even `organizationId`/`projectId` from the existing document. A partial
PUT body silently wipes every omitted field AND orphans the function from its org. This is the bug
class behind the real User Test Step rename incident (2026-07-09).

- **Never update a Common Function via `call_api` with a partial PUT.** Use
  `update_common_function` — it GETs the full document, merges the requested changes, and PUTs the
  merged whole back, so a rename is just `update_common_function(id, name="new name")`.
- **Encrypted-value mask trap**: `GET /{id}` masks encrypted-template literal values
  (`template-id-105`'s `password`, `template-id-98`'s `text`; type-0 values become all-asterisks).
  A blind GET→PUT would therefore overwrite the real stored value with `"********"`.
  `update_common_function` detects this and refuses unless the caller supplies replacement
  `steps` — vault references (type 7) are unaffected and are the better way to store credentials
  in a Common Function anyway.
- The **list endpoint only routes when `offset` is in the query string**
  (`@RequestMapping(params = "offset")`) — it's a routing key, not a paging default; the client
  always sends it.
- Create contract (from the frontend zod schema, enforced in `asset_kinds.py`): `name` 1-120 chars,
  **letters/digits/spaces/hyphens only** (no underscores/punctuation); `website_id`, `status`
  (e.g. `"READY"`), and `return_type` (`{"type": "String", "name": "", "array": false}` — only
  `type` required) are all required; `description` max 600. Nesting is rejected server-side: a
  step's `templateId` must not be another Common Function's ID.

## Eval harness (`evals/`, slice 9i, 2026-07-12)

Golden-task suite proving END-TO-END behavior against the live dev API — the runtime twin of the
planned 9h spec-drift CI. Run `./.venv/Scripts/python.exe -m evals.runner` after any CLAUDE.md/
skill/validator/client change or backend deploy; results append to `evals/results.jsonl` (the
trend history is the deliverable — a dropped check or a jump in calls/seconds vs earlier lines is
a regression). 5 tasks: login_script (full generation path), archive_restore, vc_pr_flow,
uts_rename (the destructive-PUT regression test), global_param. Tasks create `EVAL-9i …`-named
throwaways and clean up best-effort (`d.try_call`). NOT part of pytest — it hits the live API.

Trap found by the harness itself: **`DELETE /rest/api/epics/{id}` on an epic WITH stories returns
202 and silently deletes NOTHING** ("This Epic is associated with…") — pass `?force=true` (or use
`/deleteAnyway`) to actually cascade-archive. An empty epic deletes fine without force, which is
why the 9b live test never hit this.

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
| `get_ahq_context` | Always call first — loads project snapshot, including API collections/workflows/performance bots (added 2026-07-10; previously mtaf-core was entirely missing from this snapshot) |
| `crawl_url` | Discover pages + locators from a live URL |
| `create_website` / `create_page` / `add_locators` | Build UI component library |
| `search_step_templates` / `list_step_templates` / `get_step_template` | Resolve a real `templateId` before writing any test step |
| `list_epics` / `create_epic` / `list_stories` / `create_story` | Resolve or create the `story_id` a test script requires (`create_epic`/`create_story` added 2026-07-10 — previously dead code with no tool wired up; `list_stories` previously had no tool at all) |
| `create_test_script` | Add a new test script — `website_id`/`story_id` are now hard-required and validated locally before the API call (see "API Field Reference" above) |
| `list_recorded_scripts` / `get_recorded_script` / `promote_recorded_script` | Recorder-extension captures; promote turns one into a real Test Script (`story_id` required first time — see Recorded Scripts section) |
| `list_common_functions` / `get_common_function` / `create_common_function` / `update_common_function` | Reusable User Test Steps; `update_common_function` is the ONLY safe way to rename/edit one (see destructive-PUT trap section) |
| `list_archived_assets` / `restore_asset` / `permanently_delete_asset` | Administration → Archive across 10 entity types (see Archive Manager section; permanent delete is irreversible) |
| `list_project_roles` / `create_project_role` / `update_project_role_permissions` / `delete_project_role` / `assign_project_role` / `list_project_members` | Project role definitions + user assignments (see Project Roles section; VIEW is never implicit, names immutable) |
| `list_branches` / `get_scripts_for_branch` / `create_branch` / `commit_branch` / `list_commits` | Version-control branches & commits (see Version Control section; create_branch is two-phase) |
| `create_pull_request` / `list_pull_requests` / `get_pull_request` / `get_pull_request_diff` / `approve_pull_request` / `request_pr_changes` / `merge_pull_request` / `close_pull_request` | PR lifecycle (no request bodies on lifecycle actions; conflicts → UI) |
| `get_tunnel_status` / `start_tunnel` / `stop_tunnel` / `execute_tunnel_command` | Tunnel control (see Tunnel Commands note — dev gateway currently 403s all tunnel tokens) |
| `list_bots` / `execute_bot` | Run a TestBot by name |
| `get_execution_report` | View pass/fail results by `execution_id` (bug fix 2026-07-10 — previously called a nonexistent client method and always threw `AttributeError`) |
| `schedule_bot_recurring` | Set up a cron schedule |
| `test_api_request` / `test_workflow` / `run_performance_bot` | API/load testing — see mtaf-core section above |
| `get_service_spec` / `call_api` | Discover and call any AHQ endpoint not covered by a hand-written tool |

## Pre-flight validation (2026-07-10)

Every tool that creates/schedules something (`create_test_script`, `create_suite`,
`add_scripts_to_suite`, `schedule_bot_recurring`/`schedule_bot_once`, `create_api_collection`,
`create_api_request`, `create_workflow`, `create_epic`, `create_story`,
`promote_recorded_script`, `create_common_function`/`update_common_function`) is now validated in
`src/schema/asset_kinds.py` before `_dispatch` calls the client/API — a bad payload returns a
clean `{"error": "..."}` immediately instead of a live 500 or a silently broken asset. These rules
were ported directly from `automationhq-frontend-v2`'s zod form schemas, not invented — that
frontend is the actual enforced contract in this platform, since `ahq-data-commons` entities carry
no validation of their own. See `src/schema/asset_kinds.py` for the full rule set per tool.
As of 2026-07-12 every §13 backlog slice is built (9a Recorded Script + Common Function,
9b Archive Manager, 9c Project Roles, 9d Version Control v1, 9e Tunnel, 9f plugin packaging) —
still missing: conflict resolution (9d-ii), drift-detection CI (9h, needs GitHub), TestBot
creation, and a real execution-config/environments source.
