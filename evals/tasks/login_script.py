"""
Golden task: the full script-generation path — epic/story, website, page + locators,
then a 5-step login script assembled from built-in templates, verified by reading it back
the way the UI would see it. This is the exact flow that used to produce invisible or
"(Pending)"-titled scripts before the validation layer existed.
"""

TVP = "ai.automationhq.commons.entities.assets.TypeValuePair"
UIL = "ai.automationhq.commons.entities.assets.UILocator"


async def run(d) -> list[tuple[str, bool]]:
    checks = []
    sfx = d.run_suffix
    epic_id = website_id = None
    try:
        epic = await d.call("create_epic", {"name": f"EVAL-9i login {sfx}"})
        epic_id = epic.get("epicId") or epic.get("id")
        story = await d.call("create_story", {"epic_id": epic_id, "name": f"EVAL-9i story {sfx}"})
        story_id = story.get("storyId") or story.get("id")

        site = await d.call("create_website", {"name": f"EVAL-9i site {sfx}", "url": "https://eval.example.com"})
        website_id = site.get("websiteId") or site.get("id")
        page = await d.call("create_page", {"website_id": website_id, "name": "Login Page", "url": "https://eval.example.com/login"})
        page_id = page.get("pageId") or page.get("id")

        await d.call("add_locators", {
            "page_id": page_id, "website_id": website_id,
            "page_url": "https://eval.example.com/login", "page_name": "Login Page",
            "locators": [
                {"locatorName": "Email input", "locatorType": "input",
                 "locationStrategies": [{"locateBy": "css", "locatorValue": "#email", "selected": True}]},
                {"locatorName": "Password input", "locatorType": "input",
                 "locationStrategies": [{"locateBy": "css", "locatorValue": "#password", "selected": True}]},
                {"locatorName": "Sign In button", "locatorType": "button",
                 "locationStrategies": [{"locateBy": "css", "locatorValue": "button[type='submit']", "selected": True}]},
            ],
        })
        pages = await d.call("list_pages", {"website_id": website_id})
        real_page = next((p for p in pages if p.get("pageId") == page_id), None)
        locs = {l["locatorName"]: l["locatorId"] for l in (real_page or {}).get("locators", [])}
        checks.append(("3 locators created and readable", len(locs) == 3))
        if len(locs) != 3:
            return checks

        steps = [
            {"templateId": "template-id-1", "templateTitle": "Open Web Browser and go to page {{text}}",
             "sequence": 1, "parameters": [
                 {"key": "text", "value": {"type": 0, "value": "https://eval.example.com/login"}, "paramClass": TVP}]},
            {"templateId": "template-id-3", "templateTitle": "Enter {{text}} for the {{ui-locator}}",
             "sequence": 2, "parameters": [
                 {"key": "text", "value": {"type": 0, "value": "eval@example.com"}, "paramClass": TVP},
                 {"key": "ui-locator", "value": {"locatorId": locs["Email input"]}, "paramClass": UIL}]},
            {"templateId": "template-id-105", "templateTitle": "Enter encrypted text {{password}} for {{ui-locator}}",
             "sequence": 3, "parameters": [
                 {"key": "password", "value": {"type": 0, "value": "eval-not-a-real-secret"}, "paramClass": TVP},
                 {"key": "ui-locator", "value": {"locatorId": locs["Password input"]}, "paramClass": UIL}]},
            {"templateId": "template-id-4", "templateTitle": "Click {{ui-locator}}",
             "sequence": 4, "parameters": [
                 {"key": "ui-locator", "value": {"locatorId": locs["Sign In button"]}, "paramClass": UIL}]},
            {"templateId": "template-id-35", "templateTitle": "Wait for {{number}} seconds",
             "sequence": 5, "parameters": [
                 {"key": "number", "value": {"type": 0, "value": "5"}, "paramClass": TVP}]},
        ]
        script = await d.call("create_test_script", {
            "name": f"EVAL-9i Login Happy Path {sfx}", "steps": steps,
            "website_id": website_id, "story_id": story_id,
        })
        script_id = script.get("testScriptId") or script.get("id")
        checks.append(("script created", bool(script_id)))
        if not script_id:
            return checks

        back = await d.call("get_test_script", {"script_id": script_id})
        back_steps = back.get("testSteps") or []
        titles = [s.get("testStepTitle") or "" for s in back_steps]
        checks.append(("read-back has 5 steps", len(back_steps) == 5))
        checks.append(("visible in UI (websiteId set)", bool(back.get("websiteId"))))
        checks.append(("visible in UI (storyId set)", bool(back.get("storyId"))))
        checks.append(("no '(Pending)' step titles", all("(Pending)" not in t for t in titles)))
        checks.append(("on main branch explicitly", back.get("currentBranchName") == "main"))
        return checks
    finally:
        # Best-effort cleanup: deleting the epic cascades stories+scripts into the archive;
        # then purge epic + website from the archive so re-runs start clean. try_call retries
        # once — the cascade archival is asynchronous and can race an immediate purge.
        if epic_id:
            # force=true is REQUIRED here: plain DELETE on an epic WITH stories returns 202
            # with a "has associations" warning and silently deletes nothing (EpicController
            # soft-blocks instead of erroring — found live by this very task).
            await d.try_call("call_api", {"service": "test-mgmt", "method": "DELETE",
                                          "path": f"/rest/api/epics/{epic_id}", "params": {"force": "true"}})
            await d.try_call("permanently_delete_asset", {"entity_type": "epic", "asset_id": epic_id})
        if website_id:
            await d.try_call("call_api", {"service": "asset", "method": "DELETE", "path": f"/rest/api/websites/{website_id}"})
            await d.try_call("permanently_delete_asset", {"entity_type": "website", "asset_id": website_id})
