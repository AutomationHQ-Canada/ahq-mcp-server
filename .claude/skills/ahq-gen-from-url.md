---
name: ahq-gen-from-url
description: Generate AHQ test scripts by crawling a live web application URL
tools:
  - mcp__ahq-mcp-server__crawl_url
  - mcp__ahq-mcp-server__create_website
  - mcp__ahq-mcp-server__create_page
  - mcp__ahq-mcp-server__add_locators
  - mcp__ahq-mcp-server__create_test_script
---

## When to use this skill
The user has a deployed web application and wants test scripts generated automatically from a live URL.

## What to collect before starting
- Target URL (required)
- Login credentials: username + password (optional — ask only if the app requires login to reach testable content)

## Workflow

1. Call `crawl_url` with the provided URL and credentials (if any)

2. Review the crawl result:
   - If any page has `passes_threshold: false` (resolution_rate < 0.80), skip it and note it in the final summary
   - If ALL pages fail the threshold, stop and report to the user

3. For the first valid page, call `create_website` using the root domain as the name and the root URL

4. For each valid page:
   a. Call `create_page` with the page URL and title as the name, linked to the website
   b. Call `add_locators` with that page's valid locators

5. Analyze all pages together and identify testable flows:
   - Login / logout
   - Navigation flows between pages
   - Form submissions (create, update, search)
   - Validation (empty fields, invalid input, required fields)
   - Any visible CRUD operations

6. For each flow, call `create_test_script` with:
   - Name format: "<PageName> — <FlowType>" (e.g. "Login Page — Happy Path")
   - Steps built from the locators captured, using AHQ action types:
     navigate / click / type / assert-text / assert-element / select-option / wait-for-element

7. Return a summary to the user:
   - Pages crawled (total, skipped)
   - Total locators captured
   - Scripts created (list each by name)

## Rules
- Maximum 20 pages per invocation
- Never create a script with 0 steps
- Script names must be unique — append " (2)", " (3)" if duplicates arise
- If crawl returns an error for a page, skip it silently and note it in the summary
- Do not call `create_website` more than once per invocation — reuse the websiteId for all pages
