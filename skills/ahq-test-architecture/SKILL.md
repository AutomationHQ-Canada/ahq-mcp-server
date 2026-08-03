---
name: ahq-test-architecture
description: Discover a modular test architecture for a live application (crawl → modules → Epics/Stories), ported from testbotsai's Agent #1 "The Architect"
tools:
  - mcp__ahq-mcp-server__get_context
  - mcp__ahq-mcp-server__crawl_url
  - mcp__ahq-mcp-server__create_website
  - mcp__ahq-mcp-server__create_page
  - mcp__ahq-mcp-server__add_locators
  - mcp__ahq-mcp-server__list_epics
  - mcp__ahq-mcp-server__create_epic
  - mcp__ahq-mcp-server__list_stories
  - mcp__ahq-mcp-server__create_story
---

## When to use this skill
The user wants a **test strategy / modular breakdown** of a live application — "what are the
testable areas of this app and how should we organize coverage" — before (or instead of) jumping
straight to individual test scripts. Run this BEFORE `ahq-gen-from-url` when the user's ask is
architectural ("map out a test plan for X", "what should we test on this app") rather than
"generate test scripts for X".

This is the AHQ-native equivalent of testbotsai's Agent #1 ("The Architect"): same grounding
discipline and module schema, but crawling with AHQ's own `crawl_url` and persisting the result as
real Epics/Stories instead of a standalone UI artifact.

## What to collect before starting
- Target URL (required)
- Login credentials: username + password (optional — see the login limitation below before promising authenticated coverage)
- Roughly how many pages to sample (optional — default 5; `crawl_url` itself caps at 20)

## Known limitation — read before crawling with credentials
`crawl_url`'s login step only handles a **single-step** form (email + password on one page,
submitted together). It does **not** handle multi-step login (email → "Next" → password) or
SSO-only sites ("Sign in with Google/Microsoft") — on those, the login silently fails to
authenticate and the crawl falls back to whatever pages are reachable pre-login, with no explicit
signal that this happened. **Always check this yourself**: after `crawl_url` returns, if none of
the returned pages look like authenticated/internal views (e.g. everything still looks like a
marketing site or a login screen), treat the crawl as unauthenticated and say so plainly — never
present a logged-out crawl as if it were the full application's architecture. Add an
"Authentication" module flagged `needs manual verification` in that case instead of guessing what
lives behind the login.

## Workflow

1. Call `get_context` — load existing epics/stories/websites so modules aren't duplicated
   against something that already exists in the project.

2. Call `crawl_url(url, credentials, max_pages)`. This is the same crawler `ahq-gen-from-url`
   uses — real pages, titles, and locators, not a second/separate crawl implementation.

3. **Apply grounding rules before writing anything** (ported directly from testbotsai's
   `agent_test_architecture` prompt — this is the core value being carried over):
   - Only produce modules, sub-modules, and test areas for pages/nav-labels/forms that actually
     appear in the `crawl_url` result. Never invent a module because apps "usually have" it
     (no "Settings" or "Search" module unless a page/form for it was actually crawled).
   - Use the exact page `title` and URL path from the crawl — not a paraphrase.
   - If login failed or wasn't attempted, only public pages were seen. Say so explicitly and add
     an `Authentication` module (`priority: high`, flagged for manual verification) rather than
     inferring what the authenticated app contains.
   - It is far better to return 3-4 accurate modules than 10 generic ones that don't match the
     real app.

4. **Group crawled pages into modules.** Cluster pages that share a nav-label prefix or a URL
   path segment (e.g. everything under `/admin/*` or `/settings/*`) into one module; a page with
   no clear sibling is its own module. For each module produce:
   - `name` — derived from the shared nav label or path segment
   - `description` — one line, grounded in what the pages actually show
   - `subModules` — the distinct pages/sub-paths inside it
   - `testAreas` — concrete scenario names derived from that module's actual forms/CRUD
     affordances seen in the crawl (e.g. "Create <entity>", "Edit <entity>", "Required-field
     validation on <form name>") — not generic placeholders
   - `priority` — `high` for anything with a create/update/delete form or the primary post-login
     landing page, `medium` for read-only list/detail views, `low` for static/informational pages
   - `estimatedTests` — a rough count based on the number of forms and distinct interactive
     actions on that module's pages

5. **Show the modules to the user as a table before creating anything** — this is a review
   checkpoint, the same discipline `ahq-gen-from-requirements` uses for its traceability matrix.
   Wait for confirmation (or edits) before step 6.

6. On confirmation, persist the architecture into AHQ's real domain model:
   - `create_website` for the app if one doesn't already exist for this URL (check
     `get_context`/`list_websites` first — don't duplicate)
   - `create_page` + `add_locators` per crawled page, exactly as `ahq-gen-from-url` does, so the
     locators captured here are immediately usable when scripts are generated later
   - `create_epic(name=module.name)` per module. **AHQ epics only carry a `name` field** — there
     is nowhere to store `description`/`priority`/`estimatedTests` on the entity itself, so those
     stay in your response text, not in the API call.
   - `create_story(epic_id, name=testArea)` per test area under that module's epic

7. Return to the user:
   - The designed architecture (modules → sub-modules → test areas, with priority/estimatedTests)
   - What was actually persisted: N epics, M stories, pages/locators captured
   - Any modules flagged for manual review (login failed/SSO, or pages with a locator
     `resolution_rate` below 0.5 — still real pages, just worth a second look)
   - Suggest the natural next step: run `ahq-gen-from-url` (it can reuse the website/pages/locators
     just created) to turn these stories into actual test scripts

## Rules
- Never invent a module or test area for something not observed in the `crawl_url` result — same
  grounding discipline as `ahq-gen-from-url`'s locator rules, one layer up (features, not elements)
- Always show the module design and get confirmation before creating any Epics/Stories
- Never present an unauthenticated (login-failed or pre-login-only) crawl as if it captured the
  full application — flag it and add a manual-verification `Authentication` module instead
- Don't try to force `description`/`priority`/`estimatedTests` into Epic/Story fields that don't
  exist — keep that detail in your response, not the API payload
- Keep it to roughly 3-8 modules for one app; if `crawl_url` hit its own 20-page cap, say so —
  pages beyond that were never seen
- This skill stops at Epics/Stories — it does not write Test Scripts itself; hand off to
  `ahq-gen-from-url`/`ahq-gen-from-requirements` for that
