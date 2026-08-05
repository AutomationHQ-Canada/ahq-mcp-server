---
name: testbots-schedule-bot
description: Schedule a TestBot to run on a recurring cron schedule
tools:
  - mcp__testbots-mcp-server__get_context
  - mcp__testbots-mcp-server__list_grids
  - mcp__testbots-mcp-server__get_grid_capabilities
  - mcp__testbots-mcp-server__convert_text_to_cron
  - mcp__testbots-mcp-server__list_scheduler_recipient_emails
  - mcp__testbots-mcp-server__schedule_bot_recurring
  - mcp__testbots-mcp-server__list_schedulers
  - mcp__testbots-mcp-server__cancel_schedule
---

## When to use this skill
The user wants to schedule a bot to run automatically on a recurring cron schedule.

## What to collect before starting
- Bot name (required)
- Environment name (optional — defaults to first available)
- Cron expression or plain English (e.g. "every night at midnight", "every Monday at 9am") —
  if the user gives a timezone (e.g. "8pm IST"), pass that straight to `convert_text_to_cron`
  rather than hand-converting; it returns the correct UTC cron.
- A schedule name (required by the tool — ask, or derive one like "`<bot> Daily 9am`")
- Browser + OS/platform for the run (ask, or default to Chrome + latest, confirming with the
  user) — these aren't optional extras, they're required fields on the underlying tool

## Workflow

1. Call `get_context` — get bots and environments
2. Find bot and environment by name from context
3. Call `list_grids` to find a grid for this project, then `get_grid_capabilities(grid_id,
   browser)` to get valid osType/browserVersion values
4. Convert plain English (with timezone) to cron via `convert_text_to_cron` if needed
5. Confirm the full picture back to the user (bot, environment, cron in plain English,
   browser/OS, notification email) before creating
6. Call `schedule_bot_recurring(bot_id, name, cron, execution_configuration={baseUrl:
   <environment_id>, browser, browserVersion, osType, gridId}, emails=[...])` — `emails` is
   optional but check `list_scheduler_recipient_emails` for a previously-used address first
   rather than asking cold
7. Return confirmation: bot name, environment, schedule in human-readable form

## No one-time scheduling
There is no reliable one-time-schedule tool on this platform — `schedule_bot_once` was removed
(2026-07-15): it wrote to a UI-invisible mechanism that reported success but never actually
executed. If the user wants a single future run, use `execute_bot` at the right time instead.

## Common cron expressions
- Every night at midnight: `0 0 * * *`
- Every day at 9am: `0 9 * * *`
- Every Monday at 8am: `0 8 * * 1`
- Every hour: `0 * * * *`
- Every weekday at 6pm: `0 18 * * 1-5`

## Rules
- Always confirm the schedule back to the user in plain English before creating it
- Never expose raw IDs — use names only
- If the user says "cancel"/"delete the schedule(s)": `get_context` does NOT include
  scheduler data — call `list_schedulers` (optionally filtered by `bot_id`) to resolve the
  schedule name(s) the user means to a `schedulerId`, then `cancel_schedule(schedule_id)`. If a
  bot has multiple schedules and the user just says "the scheduler" ambiguously, list them and
  confirm which one(s) before deleting.
