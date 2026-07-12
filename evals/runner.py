"""
Eval runner — executes golden tasks against the LIVE dev API, scores them, and appends
results to evals/results.jsonl. See evals/README.md for when and why.

Usage:
    python -m evals.runner                 # all tasks
    python -m evals.runner login_script    # subset by name
"""

import asyncio
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.mcp_server import _dispatch, DEFAULT_BUNDLE
from evals.tasks import TASKS

RESULTS_PATH = Path(__file__).parent / "results.jsonl"


class CountingDispatcher:
    """
    Wraps _dispatch so every tool call a task makes is counted — the 'calls' column is the
    efficiency measure (a flailing workflow burns calls on retries and rediscovery).
    """

    def __init__(self):
        self.calls = 0
        self.errors: list[str] = []
        # short unique suffix so re-runs never collide with a previous run's leftovers
        self.run_suffix = uuid.uuid4().hex[:8]

    async def call(self, tool_name: str, args: dict):
        self.calls += 1
        result = await _dispatch(tool_name, args, DEFAULT_BUNDLE)
        if isinstance(result, dict) and "error" in result:
            self.errors.append(f"{tool_name}: {str(result['error'])[:150]}")
        return result

    async def try_call(self, tool_name: str, args: dict, retries: int = 1, delay: float = 2.0):
        # For cleanup paths ONLY: a failed cleanup must never destroy the task's scored checks
        # (found live: epic cascade-DELETE archives asynchronously, so an immediate permanent
        # delete can race it with "Epic is not archived" — retried once after a short wait).
        for attempt in range(retries + 1):
            try:
                return await self.call(tool_name, args)
            except Exception as e:
                if attempt == retries:
                    self.errors.append(f"cleanup {tool_name}: {str(e)[:150]}")
                    return None
                await asyncio.sleep(delay)

    @property
    def credentials(self):
        return DEFAULT_BUNDLE.test_mgmt._credentials


async def run_task(name: str, task_fn) -> dict:
    d = CountingDispatcher()
    started = time.monotonic()
    checks: list[tuple[str, bool]] = []
    fatal = None
    try:
        checks = await task_fn(d)
    except Exception as e:  # a crash is a failed task, not a crashed harness
        fatal = f"{type(e).__name__}: {str(e)[:300]}"
    seconds = round(time.monotonic() - started, 1)

    passed_checks = sum(1 for _, ok in checks if ok)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "task": name,
        "passed": fatal is None and checks != [] and passed_checks == len(checks),
        "checks_passed": passed_checks,
        "checks_total": len(checks),
        "tool_calls": d.calls,
        "seconds": seconds,
        "failed_checks": [label for label, ok in checks if not ok],
        "tool_errors": d.errors,
        "fatal": fatal,
    }
    return record


async def main(selected: list[str]):
    names = selected or list(TASKS)
    unknown = [n for n in names if n not in TASKS]
    if unknown:
        print(f"Unknown task(s): {unknown}. Available: {list(TASKS)}")
        sys.exit(2)

    records = []
    for name in names:
        print(f"running {name} ...", flush=True)
        records.append(await run_task(name, TASKS[name]))

    with RESULTS_PATH.open("a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    print(f"\n{'task':<18}{'pass':<7}{'checks':<9}{'calls':<8}{'seconds'}")
    print("-" * 52)
    for r in records:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"{r['task']:<18}{status:<7}{r['checks_passed']}/{r['checks_total']:<7}"
              f"{r['tool_calls']:<8}{r['seconds']}")
    for r in records:
        if not r["passed"]:
            print(f"\n[{r['task']}] failed checks: {r['failed_checks']}")
            if r["fatal"]:
                print(f"[{r['task']}] fatal: {r['fatal']}")
            for e in r["tool_errors"]:
                print(f"[{r['task']}] tool error: {e}")

    print(f"\nappended {len(records)} line(s) to {RESULTS_PATH}")
    sys.exit(0 if all(r["passed"] for r in records) else 1)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
