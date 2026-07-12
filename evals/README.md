# Eval harness (slice 9i)

Golden-task suite that proves the END-TO-END outcome of the MCP tool surface against the live
dev API — the runtime twin of the (planned) 9h spec-drift CI. The pytest suite proves the
plumbing (URLs, headers, bodies, validation); this proves the *behavior*: "a login script
created through these tools is actually correct and visible."

**This hits the LIVE dev gateway** (credentials from `.env`) and creates real assets — every
task creates its own clearly-named throwaway artifacts (`EVAL-9i …`) and cleans them up in a
`finally` block. It is intentionally NOT part of `pytest`; run it on purpose:

```
./.venv/Scripts/python.exe -m evals.runner            # run all tasks
./.venv/Scripts/python.exe -m evals.runner login_script archive_restore   # subset
```

Each run appends one JSON line per task to `evals/results.jsonl` (committed on purpose — the
trend over time IS the deliverable) and prints a scoreboard:

```
task              pass   checks   calls   seconds
login_script      PASS   6/6      11      8.4
archive_restore   PASS   5/5       7      4.1
...
```

## When to run it

- after any CLAUDE.md / skill / validator / client change
- after any AHQ backend deploy you hear about
- before presenting or demoing

A drop in `checks` or a jump in `calls`/`seconds` against the previous lines in results.jsonl
is a regression — root-cause it before it reaches a user.

## The golden tasks

| task | proves | scored checks |
|---|---|---|
| `login_script` | the full script-generation path | page+locators created, script created, read-back has websiteId+storyId, 5 steps, no "(Pending)" titles |
| `archive_restore` | Archive Manager lifecycle | archived visible, restore works, permanent delete empties archive |
| `vc_pr_flow` | version control v1 | branch created, commit lands, PR opens with right branches, diff non-empty, close leaves branch |
| `uts_rename` | the destructive-PUT fix | rename changes name and ONLY name — steps/params/returnType/org linkage survive |
| `global_param` | config get-merge safety | add preserves existing params, search finds it, flatten-delete removes only it |

Adding a task: drop a module in `evals/tasks/` exposing `async def run(d) -> list[(label, bool)]`
(use `d.call(tool_name, args)` for every tool call so it's counted) and register it in
`evals/tasks/__init__.py`.
