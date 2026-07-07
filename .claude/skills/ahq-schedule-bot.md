---
name: ahq-schedule-bot
description: Schedule an AHQ test bot to run on a recurring cron schedule or once at a specific time
tools:
  - mcp__ahq-mcp-server__get_ahq_context
  - mcp__ahq-mcp-server__schedule_bot_recurring
  - mcp__ahq-mcp-server__schedule_bot_once
  - mcp__ahq-mcp-server__cancel_schedule
---

## When to use this skill
The user wants to schedule a bot to run automatically — either on a recurring schedule or once at a specific time.

## What to collect before starting
- Bot name (required)
- Environment name (optional — defaults to first available)
- Schedule type: recurring or one-time
- For recurring: cron expression or plain English (e.g. "every night at midnight", "every Monday at 9am")
- For one-time: date and time

## Workflow

1. Call `get_ahq_context` — get bots and environments
2. Find bot and environment by name from context
3. Determine schedule type from user input:
   - Recurring → convert plain English to cron if needed, call `schedule_bot_recurring(bot_id, env_id, cron)`
   - One-time → convert date/time to epoch milliseconds, call `schedule_bot_once(bot_id, env_id, epoch_ms)`
4. Return confirmation: bot name, environment, schedule in human-readable form

## Common cron expressions
- Every night at midnight: `0 0 * * *`
- Every day at 9am: `0 9 * * *`
- Every Monday at 8am: `0 8 * * 1`
- Every hour: `0 * * * *`
- Every weekday at 6pm: `0 18 * * 1-5`

## Rules
- Always confirm the schedule back to the user in plain English before creating it
- Never expose raw IDs — use names only
- If user says "cancel the schedule", call `cancel_schedule(schedule_id)` from context
