"""
Golden task: version-control v1 happy path — create branch, commit, open a PR to main,
diff it, close it (never merge — merging would modify main), delete the branch.
"""


async def run(d) -> list[tuple[str, bool]]:
    checks = []
    sfx = d.run_suffix
    branch = f"eval-9i-{sfx}"
    project_id = d.credentials.project_id
    branch_created = False
    try:
        created = await d.call("create_branch", {"branch_name": branch})
        if created.get("status") == "NEEDS_CONFIRMATION":
            created = await d.call("create_branch", {"branch_name": branch, "confirmed": True})
        branch_created = created.get("status") == "CREATED"
        checks.append(("branch created", branch_created))
        if not branch_created:
            return checks

        commit = await d.call("commit_branch", {"branch_name": branch, "message": f"EVAL-9i commit {sfx}"})
        checks.append(("commit created", bool(commit.get("commitId"))))

        pr = await d.call("create_pull_request", {
            "source_branch": branch, "target_branch": "main",
            "title": f"EVAL-9i PR {sfx} - will be closed",
        })
        pr_id = pr.get("prId")
        checks.append(("PR opened with correct branches",
                       bool(pr_id) and pr.get("sourceBranch") == branch and pr.get("targetBranch") == "main"))
        if pr_id:
            diff = await d.call("get_pull_request_diff", {"pr_id": pr_id})
            checks.append(("PR diff readable", isinstance(diff, dict) and "scriptDiffs" in diff))
            closed = await d.call("close_pull_request", {"pr_id": pr_id})
            checks.append(("PR closed without merging", closed.get("status") == "CLOSED"))

        after = await d.call("list_branches", {"query": branch})
        checks.append(("source branch survives PR close", any(b.get("branchName") == branch for b in after)))
        return checks
    finally:
        if branch_created:
            await d.try_call("call_api", {
                "service": "test-mgmt", "method": "DELETE",
                "path": f"/rest/api/projects/{project_id}/branches", "params": {"branchName": branch},
            })
