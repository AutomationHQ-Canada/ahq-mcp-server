"""
Golden task: Archive Manager lifecycle on a throwaway epic —
module DELETE archives it, restore brings it back, permanent delete empties the archive.
"""


async def run(d) -> list[tuple[str, bool]]:
    checks = []
    sfx = d.run_suffix
    name = f"EVAL-9i archive {sfx}"
    epic_id = None
    try:
        epic = await d.call("create_epic", {"name": name})
        epic_id = epic.get("epicId") or epic.get("id")
        checks.append(("epic created", bool(epic_id)))
        if not epic_id:
            return checks

        await d.call("call_api", {"service": "test-mgmt", "method": "DELETE", "path": f"/rest/api/epics/{epic_id}"})
        archived = await d.call("list_archived_assets", {"entity_type": "epic", "search": f"EVAL-9i archive {sfx}"})
        found = any((e.get("epicId") or e.get("id")) == epic_id for e in archived.get("content", []))
        checks.append(("archived epic visible in Archive Manager", found))

        restored = await d.call("restore_asset", {"entity_type": "epic", "asset_id": epic_id})
        checks.append(("restore reports success", restored.get("success") is True))
        epics = await d.call("list_epics", {})
        back = any((e.get("epicId") or e.get("id")) == epic_id for e in epics)
        checks.append(("restored epic back in module listing", back))

        await d.call("call_api", {"service": "test-mgmt", "method": "DELETE", "path": f"/rest/api/epics/{epic_id}"})
        purged = await d.call("permanently_delete_asset", {"entity_type": "epic", "asset_id": epic_id})
        checks.append(("permanent delete reports success", purged.get("success") is True))
        epic_id = None  # nothing left to clean
        return checks
    finally:
        if epic_id:
            await d.try_call("call_api", {"service": "test-mgmt", "method": "DELETE", "path": f"/rest/api/epics/{epic_id}"})
            await d.try_call("permanently_delete_asset", {"entity_type": "epic", "asset_id": epic_id})
