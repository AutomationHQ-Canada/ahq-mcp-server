---
name: ahq-gen-from-requirements
description: Generate AHQ test scripts from a requirements document (PDF/DOCX/XLSX/CSV/TXT)
tools:
  - mcp__ahq-mcp-server__extract_requirements
  - mcp__ahq-mcp-server__get_ahq_context
  - mcp__ahq-mcp-server__list_epics
  - mcp__ahq-mcp-server__search_step_templates
  - mcp__ahq-mcp-server__get_step_template
  - mcp__ahq-mcp-server__create_test_script
  - mcp__ahq-mcp-server__create_suite
  - mcp__ahq-mcp-server__add_scripts_to_suite
---

## When to use this skill
The user has a requirements doc, user story export, or spec file and wants AHQ test scripts
generated from it — no live app/URL involved.

## What to collect before starting
- Absolute path to the requirements file (required)
- Which epic/story to attach the scripts to, if any (optional — ask, don't guess)

## Workflow

1. Call `get_ahq_context` — load existing epics/bots/suites so generated scripts don't duplicate
   something that already exists.
2. Call `extract_requirements` with the file path.
   - The tool only parses the file — it does not generate test cases. That reasoning happens here.
   - `.pdf`/`.docx`/`.txt`/`.md` return `raw_text` (and `.docx` also returns `sections` by heading).
   - `.csv` returns `rows` (list of dicts keyed by header) — treat each row as one requirement/story.
   - `.xlsx` returns `sheets` (sheet name → rows) — ask the user which sheet if more than one has content.
   - If the result has an `error` key, stop and report it to the user (bad path, unsupported type, or
     file too large) rather than guessing at a fix.

3. Read the extracted content and identify discrete requirements — each row (CSV/XLSX), each heading
   section (DOCX), or each paragraph/numbered item (PDF/TXT) that describes a single piece of
   behavior.

4. For each requirement, derive one or more Given/When/Then test cases:
   - **Given** — preconditions / starting state
   - **When** — the user action being tested
   - **Then** — the expected observable outcome
   - Assign a **priority**: `critical` (core flow, blocks release), `high` (common path), `medium`
     (edge case), `low` (cosmetic/rare). Base it on language cues in the requirement (e.g. "must",
     "shall" → critical/high; "may", "optional" → low) — do not invent a priority scheme per file.

5. Build a **traceability matrix** before creating anything: one row per requirement showing
   `requirement_id/heading → test case name(s) → priority`. Show this to the user for confirmation
   before writing scripts, since requirements → test case mapping is not always 1:1.

6. For each concrete UI action a test case needs, call `search_step_templates` to get the real
   `templateId` AND `templateTitle` — templates are live per-project data (built-ins plus
   org-defined Common Functions), never a fixed list you can assume. Single-word searches work
   much better than full phrases — e.g. "Navigate" only matches back/forward history templates,
   use "Go to"/"Open" to find "Open Web Browser and go to page {{text}}"; "Enter Text" matches
   nothing, use "Enter"; "Assert Text" matches nothing, this platform uses "Verify". Call
   `get_step_template` if it's unclear which placeholder names (`{{...}}` in `templateTitle`) a
   template expects. **Never invent a templateId.**

7. Call `create_test_script` for each derived test case:
   - Name format: "<Requirement ref> — <Scenario>" (e.g. "REQ-12 — Login with invalid password")
   - Steps use the templateIds resolved above, only if concrete UI targets are known from context;
     otherwise leave the script as a single descriptive placeholder step and flag it as needing
     manual locator/template work.
   - See CLAUDE.md's "TestStep shape" section for the exact, proven-working shape. In short: each
     step needs `templateId` + `templateTitle` (built-ins only) + a `parameters` array (NOT
     `params`) with one entry per `{{placeholder}}` in `templateTitle` — `{"key": "ui-locator",
     "value": {"locatorId": "<real id>"}, "paramClass":
     "ai.automationhq.commons.entities.assets.UILocator"}` for element targets (never fabricate
     locateBy/locatorValue, the server enriches from the saved locator), and `{"key": "text",
     "value": {"type": 0, "value": "<literal>"}, "paramClass":
     "ai.automationhq.commons.entities.assets.TypeValuePair"}` for scalar values.
   - **For every built-in templateId (`"template-id-N"`), copy that template's `templateTitle`
     string verbatim into the step's `templateTitle` field** (placeholders intact) — the server
     does not look this up itself for built-ins and omitting it causes a 500 error. Not needed for
     Common-Function templateIds (real UUIDs).
   - Attach to an epic/story only if the user specified one.

8. If more than a few scripts were created, call `create_suite` and `add_scripts_to_suite` to group
   them under one suite named after the source file.

9. Return to the user:
   - The traceability matrix (requirement → test case → priority)
   - Scripts created (count + names)
   - Any requirements skipped and why (ambiguous, no clear UI target, duplicate of existing script)

## Rules
- Never fabricate UI locators that weren't derivable from context — flag those scripts instead of
  guessing (this mirrors the grounding-rules discipline used for `crawl_url`/`ahq-gen-from-url`)
- Never fabricate a templateId — always resolve it via `search_step_templates`/`get_step_template` first
- Never omit `templateTitle` on a step whose templateId is a built-in (`"template-id-N"`) — causes a 500
- Never put step values in `params` — use `parameters` (a list); `params` does not drive step titles or execution
- Never fabricate `locateBy`/`locatorValue` on a `ui-locator` parameter — pass only `{"locatorId": "..."}` and let the server enrich it
- Never create a script with 0 steps
- Script names must be unique — append " (2)", " (3)" if duplicates arise
- Always show the traceability matrix before writing scripts, not just in the final summary
- If the file has an `error` from `extract_requirements`, do not retry — report it to the user
