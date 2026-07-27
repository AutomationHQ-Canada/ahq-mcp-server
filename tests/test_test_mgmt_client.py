import httpx

from src.clients.test_mgmt_client import TestMgmtClient


def _client_with_fake_transport(fake_request):
    client = TestMgmtClient()
    client._client.request = fake_request
    return client


async def test_create_test_script_sends_testSteps_field():
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["json"] = kwargs["json"]
        return httpx.Response(200, json={"id": "s1"}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    steps = [{"templateId": "tmpl-1", "testStepTitle": "Click login"}]
    await client.create_test_script("Login Happy Path", steps, "page-1")

    assert captured["json"] == {
        "name": "Login Happy Path",
        "testSteps": steps,
        "status": "Not Started",
        "type": "WEB",
        "currentBranchName": "main",
        "pageId": "page-1",
    }


async def test_create_test_script_includes_website_id_when_given():
    # websiteId drives the UI's "Application" column/filtering and is separate from pageId —
    # a script created without it was invisible in the Table View despite existing correctly.
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["json"] = kwargs["json"]
        return httpx.Response(200, json={"id": "s1"}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    steps = [{"templateId": "tmpl-1"}]
    await client.create_test_script("Login Happy Path", steps, page_id="page-1", website_id="site-1", story_id="story-1")

    assert captured["json"] == {
        "name": "Login Happy Path",
        "testSteps": steps,
        "status": "Not Started",
        "type": "WEB",
        "currentBranchName": "main",
        "pageId": "page-1",
        "websiteId": "site-1",
        "storyId": "story-1",
    }


async def test_create_test_script_always_sends_explicit_branch_name():
    # Omitting currentBranchName lets the server fall back to this API token's ambient
    # "checked out branch" ProjectState for the project, which is NOT reliably "main" — confirmed
    # live: two scripts created back-to-back with no explicit branch landed on different branches.
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["json"] = kwargs["json"]
        return httpx.Response(200, json={"id": "s1"}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    await client.create_test_script("Some Script", [{"templateId": "tmpl-1"}])

    assert captured["json"]["currentBranchName"] == "main"


async def test_list_templates_uses_project_scoped_path():
    async def fake_request(method, url, **kwargs):
        assert method == "GET"
        assert url == "https://api-dev.automationhq.ai/ahq-test-management-services/rest/api/templates/test-project"
        assert kwargs["params"] == {"offset": 0}
        return httpx.Response(200, json={"content": [{"templateId": "tmpl-1", "templateTitle": "Click"}]}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.list_templates()

    assert result == [{"templateId": "tmpl-1", "templateTitle": "Click"}]


async def test_search_templates_sends_title_param():
    captured = []

    async def fake_request(method, url, **kwargs):
        captured.append((url, kwargs["params"]))
        return httpx.Response(200, json=[{"templateId": "tmpl-2", "templateTitle": "Navigate to URL"}], request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.search_templates("Navigate")

    search_url = "https://api-dev.automationhq.ai/ahq-test-management-services/rest/api/templates/search"
    assert all(url == search_url for url, _ in captured)
    assert {"title": "Navigate"} in [params for _, params in captured]
    # Every query returned the same record; the caller must see it once, not once per query.
    assert result == [{"templateId": "tmpl-2", "templateTitle": "Navigate to URL"}]


async def test_search_templates_expands_synonyms_for_the_platforms_own_wording():
    """"Navigate" must still reach the step that opens a URL.

    The platform titles that step "Open Web Browser and go to page", and server-side search is a
    plain substring match, so the literal query returns only "Navigate back"/"Navigate forward".
    """
    queried = []

    async def fake_request(method, url, **kwargs):
        title = kwargs["params"]["title"]
        queried.append(title)
        body = {
            "Navigate": [{"templateId": "template-id-178", "templateTitle": "Navigate back"}],
            "Open Web Browser": [{"templateId": "template-id-1", "templateTitle": "Open Web Browser and go to page {{text}}"}],
        }.get(title, [])
        return httpx.Response(200, json=body, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.search_templates("Navigate")

    assert "Navigate" in queried
    assert "Open Web Browser" in queried
    ids = [t["templateId"] for t in result]
    assert "template-id-1" in ids
    # The literal query's own hits stay ahead of anything an alias contributed.
    assert ids.index("template-id-178") < ids.index("template-id-1")


async def test_search_templates_survives_a_failing_alias_query():
    async def fake_request(method, url, **kwargs):
        if kwargs["params"]["title"] != "Navigate":
            return httpx.Response(500, json={"error": "boom"}, request=httpx.Request(method, url))
        return httpx.Response(200, json=[{"templateId": "template-id-178", "templateTitle": "Navigate back"}], request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.search_templates("Navigate")

    assert [t["templateId"] for t in result] == ["template-id-178"]


async def test_get_template_by_id():
    async def fake_request(method, url, **kwargs):
        assert url == "https://api-dev.automationhq.ai/ahq-test-management-services/rest/api/templates/tmpl-1"
        return httpx.Response(200, json={"templateId": "tmpl-1", "templateTitle": "Click", "params": [{"name": "uiLocator", "type": "STRING"}]}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.get_template("tmpl-1")

    assert result["templateId"] == "tmpl-1"
    assert result["params"][0]["name"] == "uiLocator"


# --- Scheduler — the REAL endpoint (test-management-services' /rest/api/schedulers), confirmed
# against automationhq-frontend-v2's SchedulerSchema/TSchedulerCreateSchema and its
# callSchedulerCreateApi. NOT background-v2-services' schedule-recurring/-once-at endpoints,
# which write to a different, UI-invisible mechanism that doesn't reliably fire.

async def test_create_scheduler_sends_real_endpoint_and_shape():
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["json"] = kwargs["json"]
        return httpx.Response(200, json={"schedulerId": "sched-1"}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    cfg = {"baseUrl": "env-1", "browser": "Chrome", "gridId": "grid-1", "browserVersion": "latest", "osType": "Grid OS"}
    result = await client.create_scheduler("bot-1", "Nightly Run", ["a@example.com"], "0 0 * * *", cfg)

    assert captured["method"] == "POST"
    assert captured["url"] == "https://api-dev.automationhq.ai/ahq-test-management-services/rest/api/schedulers"
    assert captured["json"] == {
        "name": "Nightly Run",
        "emails": ["a@example.com"],
        "recurringRule": "0 0 * * *",
        "executionConfiguration": cfg,
        "resourceId": "bot-1",
        "resourceType": 1,
        "organizationId": "test-org",
        "projectId": "test-project",
    }
    assert result == {"schedulerId": "sched-1"}


async def test_toggle_scheduler_sends_no_body():
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["json"] = kwargs.get("json")
        return httpx.Response(200, json={"enabled": False}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    await client.toggle_scheduler("sched-1")

    assert captured["method"] == "PATCH"
    assert captured["url"] == "https://api-dev.automationhq.ai/ahq-test-management-services/rest/api/schedulers/sched-1/toggle"
    assert captured["json"] is None


async def test_delete_scheduler_uses_real_path():
    async def fake_request(method, url, **kwargs):
        assert method == "DELETE"
        assert url == "https://api-dev.automationhq.ai/ahq-test-management-services/rest/api/schedulers/sched-1"
        return httpx.Response(200, json={"success": True}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    await client.delete_scheduler("sched-1")


_EXISTING_SCHEDULER = {
    "schedulerId": "sched-1",
    "resourceId": "bot-1",
    "resourceType": 1,
    "name": "Nightly Run",
    "emails": ["existing@example.com"],
    "recurringRule": "0 0 * * *",
    "executionConfiguration": {"baseUrl": "env-1", "browser": "Chrome", "gridId": "grid-1",
                               "browserVersion": "latest", "osType": "Grid OS"},
}


async def test_update_scheduler_merges_partial_change_over_existing_record():
    # Regression coverage for the exact destructive-PUT trap update_common_function already
    # guards against: the real endpoint takes a full-document replace, not a patch, so an update
    # that only wants to change the cron must not silently wipe emails/executionConfiguration.
    captured = {}

    async def fake_request(method, url, **kwargs):
        if method == "GET":
            return httpx.Response(200, json=_EXISTING_SCHEDULER, request=httpx.Request(method, url))
        captured["method"] = method
        captured["url"] = url
        captured["json"] = kwargs["json"]
        return httpx.Response(200, json={"schedulerId": "sched-1"}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    await client.update_scheduler("sched-1", recurring_rule="0 9 * * *")  # only the cron changes

    assert captured["method"] == "PUT"
    assert captured["url"] == "https://api-dev.automationhq.ai/ahq-test-management-services/rest/api/schedulers/sched-1"
    assert captured["json"] == {
        "name": "Nightly Run",  # preserved
        "emails": ["existing@example.com"],  # preserved
        "recurringRule": "0 9 * * *",  # the actual change
        "executionConfiguration": _EXISTING_SCHEDULER["executionConfiguration"],  # preserved
        "resourceId": "bot-1",  # preserved
        "resourceType": 1,
        "organizationId": "test-org",
        "projectId": "test-project",
    }


async def test_update_scheduler_overrides_only_explicitly_given_fields():
    async def fake_request(method, url, **kwargs):
        if method == "GET":
            return httpx.Response(200, json=_EXISTING_SCHEDULER, request=httpx.Request(method, url))
        captured["json"] = kwargs["json"]
        return httpx.Response(200, json={"schedulerId": "sched-1"}, request=httpx.Request(method, url))

    captured = {}
    client = _client_with_fake_transport(fake_request)
    await client.update_scheduler("sched-1", name="Renamed", emails=["new@example.com"])

    assert captured["json"]["name"] == "Renamed"
    assert captured["json"]["emails"] == ["new@example.com"]
    assert captured["json"]["recurringRule"] == "0 0 * * *"  # untouched, preserved from existing


async def test_list_schedulers_filters_by_bot_id_matching_ui_shape():
    # Matches ListSchedulers.tsx's own filter exactly — the TestBot scheduler drawer filters
    # strictly by resourceId == this bot's id, so this is what confirms whether a created
    # schedule actually landed against the bot the caller expected.
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["json"] = kwargs["json"]
        return httpx.Response(200, json={"content": []}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    await client.list_schedulers(bot_id="bot-1")

    assert captured["json"] == {
        "offset": 0, "size": 100, "sortBy": "createdDate", "orderBy": "desc",
        "resourceType": 1, "resourceId": "bot-1",
    }


async def test_list_schedulers_omits_resource_id_when_no_bot_given():
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["json"] = kwargs["json"]
        return httpx.Response(200, json={"content": []}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    await client.list_schedulers()

    assert "resourceId" not in captured["json"]


async def test_convert_text_to_cron_sends_locale_en():
    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["json"] = kwargs["json"]
        return httpx.Response(200, json={"success": True, "expression": "0 9 * * *"}, request=httpx.Request(method, url))

    client = _client_with_fake_transport(fake_request)
    result = await client.convert_text_to_cron("every day at 9am")

    assert captured["json"] == {"text": "every day at 9am", "locale": "en"}
    assert result["expression"] == "0 9 * * *"
