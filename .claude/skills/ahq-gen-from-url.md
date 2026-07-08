---
name: ahq-gen-from-url
description: Generate AHQ test scripts by crawling a live web application URL
tools:
  - mcp__ahq-mcp-server__crawl_url
  - mcp__ahq-mcp-server__create_website
  - mcp__ahq-mcp-server__create_page
  - mcp__ahq-mcp-server__add_locators
  - mcp__ahq-mcp-server__search_step_templates
  - mcp__ahq-mcp-server__get_step_template
  - mcp__ahq-mcp-server__create_test_script
---

## When to use this skill
The user has a deployed web application and wants test scripts generated automatically from a live URL.

## What to collect before starting
- Target URL (required)
- Login credentials: username + password (optional — ask only if the app requires login to reach testable content)

## Workflow

1. Call `get_ahq_context` — load full project snapshot (websites, envs, epics, bots, queue)
2. Call `crawl_url` with the provided URL and credentials (if any)

3. Review the crawl result:
   - If any page has `passes_threshold: false` (resolution_rate < 0.80), skip it and note it in the final summary
   - If ALL pages fail the threshold, stop and report to the user

4. For the first valid page, call `create_website` using the root domain as the name and the root URL

5. For each valid page:
   a. Call `create_page` with the page URL and title as the name, linked to the website
   b. Call `add_locators` with that page's valid locators

6. Analyze all pages together and identify testable flows:
   - Login / logout
   - Navigation flows between pages
   - Form submissions (create, update, search)
   - Validation (empty fields, invalid input, required fields)
   - Any visible CRUD operations

7. For each flow, before writing any steps, call `search_step_templates` for each action you need
   (e.g. title="Navigate", title="Click", title="Enter Text", title="Assert Text") to get the real
   `templateId` — there is no fixed/static list of action types, templates are live per-project data
   (built-ins plus org-defined Common Functions). Call `get_step_template` on the result if it's
   unclear which `params` sub-fields that template expects. **Never invent a templateId.**

8. For each flow, call `create_test_script` with:
   - Name format: "<PageName> — <FlowType>" (e.g. "Login Page — Happy Path")
   - Steps built from the locators captured and the resolved templateIds — put the locator in
     `params.uiLocator` (locateBy/locatorValue/locatorType), input values in `params.text.value`,
     assertions in `params.expected.value`

9. Return a summary to the user:
   - Pages crawled (total, skipped)
   - Total locators captured
   - Scripts created (list each by name)

## Rules
- Maximum 20 pages per invocation
- Never fabricate a templateId — always resolve it via `search_step_templates`/`get_step_template` first
- Never create a script with 0 steps
- Script names must be unique — append " (2)", " (3)" if duplicates arise
- If crawl returns an error for a page, skip it silently and note it in the summary
- Do not call `create_website` more than once per invocation — reuse the websiteId for all pages
