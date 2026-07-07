---
name: ahq-view-performance
description: Show performance and ROI metrics from a test execution
tools:
  - mcp__ahq-mcp-server__get_ahq_context
  - mcp__ahq-mcp-server__list_recent_runs
  - mcp__ahq-mcp-server__get_performance_report
---

## When to use this skill
The user wants to see performance metrics or ROI data from a test run.

## Workflow

1. Call `get_ahq_context` — get bots list
2. If no job ID provided, call `list_recent_runs(limit=1)` to get latest run
3. Call `get_performance_report(execution_id)` for metrics
4. Return human-readable summary:
   - Execution time per script
   - Pass rate trend vs previous run (if available)
   - ROI metrics if available

## Rules
- Never expose raw IDs
- If no performance data is available, say so clearly
