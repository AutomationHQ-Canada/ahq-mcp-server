"""
Golden task: the destructive-PUT fix. Rename a Common Function (User Test Step) and prove the
rename changed the name and ONLY the name — testSteps, parameters, returnType, and org/project
linkage must all survive. This is the regression test for the real 2026-07-09 wipe incident.
"""

TVP = "ai.automationhq.commons.entities.assets.TypeValuePair"


async def run(d) -> list[tuple[str, bool]]:
    checks = []
    sfx = d.run_suffix
    cf_id = None
    try:
        created = await d.call("create_common_function", {
            "name": f"EVAL-9i uts {sfx}",
            "website_id": "85ae8c02-668f-44f5-866e-0f30e353f8de",  # existing "Testing VS" website
            "status": "READY",
            "return_type": {"name": "", "type": "String", "array": False},
            "description": "EVAL-9i throwaway - safe to delete",
            "steps": [{
                "templateId": "template-id-35", "templateTitle": "Wait for {{number}} seconds",
                "sequence": 1,
                "parameters": [{"key": "number", "value": {"type": 0, "value": "3"}, "paramClass": TVP}],
            }],
            "parameters": [{"name": "eval-input", "type": "String", "array": False}],
        })
        cf_id = created.get("id")
        checks.append(("common function created", bool(cf_id)))
        if not cf_id:
            return checks

        await d.call("update_common_function", {"common_function_id": cf_id, "name": f"EVAL-9i uts renamed {sfx}"})
        after = await d.call("get_common_function", {"common_function_id": cf_id})

        checks.append(("name changed", after.get("name") == f"EVAL-9i uts renamed {sfx}"))
        checks.append(("testSteps survived", len(after.get("testSteps") or []) == 1))
        checks.append(("parameters survived", len(after.get("parameters") or []) == 1))
        checks.append(("returnType survived", (after.get("returnType") or {}).get("type") == "String"))
        checks.append(("org linkage survived", bool(after.get("organizationId")) and bool(after.get("projectId"))))
        checks.append(("status survived", after.get("status") == "READY"))
        return checks
    finally:
        if cf_id:
            await d.try_call("call_api", {"service": "asset", "method": "DELETE", "path": f"/rest/api/commonFunctions/{cf_id}"})
