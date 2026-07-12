"""
Golden task: Global Parameters get-merge safety. Adding a parameter must PRESERVE every
existing parameter (the raw endpoint replaces the whole list — the client merges), search must
find it, and flatten-and-delete must remove only it.
"""


async def run(d) -> list[tuple[str, bool]]:
    checks = []
    sfx = d.run_suffix
    pname = f"eval_9i_{sfx}"
    prop_id = None
    try:
        before = await d.call("list_global_parameters", {})
        before_names = {p.get("name") for p in (before.get("customProperties") or [])}

        await d.call("add_global_parameter", {"name": pname, "value": "eval-value", "description": "EVAL-9i throwaway"})

        after = await d.call("list_global_parameters", {})
        props = after.get("customProperties") or []
        after_names = {p.get("name") for p in props}
        checks.append(("new parameter present", pname in after_names))
        checks.append(("every pre-existing parameter preserved", before_names <= after_names))

        found = await d.call("search_global_parameters", {"name": pname})
        checks.append(("search finds it", any(p.get("name") == pname for p in found)))

        prop_id = next((p.get("customPropertyId") for p in props if p.get("name") == pname), None)
        checks.append(("has a customPropertyId", bool(prop_id)))
        if prop_id:
            await d.call("flatten_and_delete_global_parameter", {"custom_property_id": prop_id})
            final = await d.call("list_global_parameters", {})
            final_names = {p.get("name") for p in (final.get("customProperties") or [])}
            checks.append(("deleted, others intact", pname not in final_names and before_names <= final_names))
            prop_id = None
        return checks
    finally:
        if prop_id:
            await d.try_call("flatten_and_delete_global_parameter", {"custom_property_id": prop_id})
