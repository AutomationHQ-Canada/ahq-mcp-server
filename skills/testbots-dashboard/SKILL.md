---
name: testbots-dashboard
description: Show a full project overview — websites, scripts, bots, recent runs, queue state
tools:
  - mcp__ahq-mcp-server__get_context
  - mcp__ahq-mcp-server__list_recent_runs
---

## When to use this skill
The user wants a quick overview of the entire TestBots project state.

## Workflow

1. Call `get_context` — loads everything in parallel
2. Call `list_recent_runs(limit=3)` — last 3 runs across all bots
3. Return human-readable dashboard:

   Project: <name>
   User: <name>

   Assets
   ├── Websites: X
   ├── Pages: X (total across all websites)
   └── Environments: X

   Test Assets
   ├── Test Scripts: X
   ├── Bots: X (list names)
   ├── Suites: X
   └── Epics: X

   Recent Runs
   ├── <Bot Name> — <pass>/<total> passed (<rate>%) — <time ago>
   ├── <Bot Name> — <pass>/<total> passed (<rate>%) — <time ago>
   └── <Bot Name> — <pass>/<total> passed (<rate>%) — <time ago>

   Queue: idle / X jobs running

## Rules
- Show counts not raw lists — keep it scannable
- Always show pass rate as percentage
- If queue has running jobs, highlight that
- Time ago format: "2 hours ago", "yesterday", "3 days ago"
