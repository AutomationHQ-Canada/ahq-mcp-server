---
name: testbots-view-report
description: Go through a finished run's results - which steps failed, and where
tools:
  - mcp__testbots-mcp-server__get_context
  - mcp__testbots-mcp-server__list_recent_runs
  - mcp__testbots-mcp-server__get_execution_report
  - mcp__testbots-mcp-server__get_execution_screenshots
---

## When to use this skill
The user wants to see test execution results — what passed, what failed, screenshots.

## What to collect before starting
- Bot name (optional — if not provided, show last run across all bots)
- Job ID (optional — if provided, show that specific run)

## Workflow

1. Call `get_context` — get bots list and queue status
2. If no job ID provided:
   - Call `list_recent_runs(bot_id, limit=1)` to get the latest run
3. Call `get_execution_report(job_id)` for full pass/fail breakdown
4. If there are failures:
   - Call `get_execution_screenshots(execution_id)` for failure screenshots
5. Return human-readable report:
   - Run summary: bot, environment, date, duration, pass rate
   - ✅ Passed scripts (count + names)
   - ❌ Failed scripts (count + names + which step failed)
   - Screenshots for each failure

## Rules
- Always show pass rate as a percentage: "44/47 passed (93.6%)"
- For failures, show the exact step that failed and the error message
- If the last run is still in progress, show current status and elapsed time
- Never expose raw IDs — use bot/script names
