---
name: ahq-run-bot
description: Execute a TestBot immediately and report the result
tools:
  - mcp__ahq-mcp-server__get_context
  - mcp__ahq-mcp-server__execute_bot
  - mcp__ahq-mcp-server__get_job_status
  - mcp__ahq-mcp-server__get_execution_report
---

## When to use this skill
The user wants to run a test bot now and see the results.

## What to collect before starting
- Bot name (required) — e.g. "Regression Bot", "Smoke Bot"
- Environment name (optional — if not provided, use the first available environment)

## Workflow

1. Call `get_context` — get bots list and environments list
2. Find the bot by name from the context (case-insensitive match)
   - If not found: list available bots and ask user to clarify
3. Find the environment by name from the context
   - If not specified: use first environment in the list
4. Call `execute_bot(bot_id, env_id)`
5. Poll `get_job_status(job_id)` every 10 seconds until status is COMPLETED, FAILED, or CANCELLED
6. Call `get_execution_report(job_id)` for the full result
7. Return human-readable summary:
   - Bot name, environment, start time, duration
   - Total scripts: X passed, Y failed
   - List each failed script by name

## Rules
- Never expose raw IDs to the user — always use names
- If the queue is busy (from context), warn the user before executing
- If status is FAILED, show which scripts failed and suggest running /ahq-view-report for screenshots
