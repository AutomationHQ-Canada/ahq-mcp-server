from src.mcp_server import _dispatch, _get_context, _HOSTED_UNSUPPORTED, DEFAULT_BUNDLE


async def test_hosted_unsupported_tools_return_clean_error_when_hosted():
    for name in _HOSTED_UNSUPPORTED:
        result = await _dispatch(name, {}, DEFAULT_BUNDLE, is_hosted=True)
        assert "error" in result
        assert "not available over the hosted MCP server" in result["error"]


async def test_check_local_agent_status_guard_does_not_fire_when_not_hosted():
    # is_hosted=False (stdio) must NOT be short-circuited — it should reach the real client call,
    # not the "not available hosted" guard error. Monkeypatch the client method itself rather than
    # asserting on the live localhost:9202 network call, whose actual online/offline result depends
    # on whether a local agent happens to be running on the machine running this test.
    sentinel = {"online": False, "error": "sentinel-not-the-guard-error"}
    original = DEFAULT_BUNDLE.local_exec.get_agent_status
    DEFAULT_BUNDLE.local_exec.get_agent_status = lambda: _async_result(sentinel)
    try:
        result = await _dispatch("check_local_agent_status", {}, DEFAULT_BUNDLE, is_hosted=False)
    finally:
        DEFAULT_BUNDLE.local_exec.get_agent_status = original
    assert result == sentinel


async def _async_result(value):
    return value


async def test_unknown_tool_returns_error():
    result = await _dispatch("not_a_real_tool", {}, DEFAULT_BUNDLE, is_hosted=False)
    assert result == {"error": "Unknown tool: not_a_real_tool"}


async def test_create_test_script_missing_story_id_rejected_before_api_call():
    # Validation must fire before any client method runs — sabotage the client method so the
    # test fails loudly if validation is ever bypassed.
    def _boom(*a, **kw):
        raise AssertionError("client should never be called when validation fails")

    original = DEFAULT_BUNDLE.test_mgmt.create_test_script
    DEFAULT_BUNDLE.test_mgmt.create_test_script = _boom
    try:
        result = await _dispatch(
            "create_test_script",
            {"name": "A script", "steps": [{"templateId": "real-uuid"}], "website_id": "w1"},
            DEFAULT_BUNDLE, is_hosted=False,
        )
    finally:
        DEFAULT_BUNDLE.test_mgmt.create_test_script = original
    assert "error" in result
    assert "story_id" in result["error"]


async def test_create_test_script_with_all_required_fields_reaches_client():
    sentinel = {"testScriptId": "sentinel"}
    original = DEFAULT_BUNDLE.test_mgmt.create_test_script
    DEFAULT_BUNDLE.test_mgmt.create_test_script = lambda *a, **kw: _async_result(sentinel)
    try:
        result = await _dispatch(
            "create_test_script",
            {"name": "A script", "steps": [{"templateId": "real-uuid"}], "website_id": "w1", "story_id": "s1"},
            DEFAULT_BUNDLE, is_hosted=False,
        )
    finally:
        DEFAULT_BUNDLE.test_mgmt.create_test_script = original
    assert result == sentinel


async def test_create_epic_dispatches_to_client():
    sentinel = {"epicId": "e1"}
    original = DEFAULT_BUNDLE.test_mgmt.create_epic
    DEFAULT_BUNDLE.test_mgmt.create_epic = lambda name: _async_result(sentinel)
    try:
        result = await _dispatch("create_epic", {"name": "Epic 1"}, DEFAULT_BUNDLE, is_hosted=False)
    finally:
        DEFAULT_BUNDLE.test_mgmt.create_epic = original
    assert result == sentinel


async def test_list_stories_dispatches_to_client():
    sentinel = [{"storyId": "s1"}]
    original = DEFAULT_BUNDLE.test_mgmt.list_stories
    DEFAULT_BUNDLE.test_mgmt.list_stories = lambda epic_id: _async_result(sentinel)
    try:
        result = await _dispatch("list_stories", {"epic_id": "e1"}, DEFAULT_BUNDLE, is_hosted=False)
    finally:
        DEFAULT_BUNDLE.test_mgmt.list_stories = original
    assert result == sentinel


async def test_create_story_dispatches_to_client():
    sentinel = {"storyId": "s1"}
    original = DEFAULT_BUNDLE.test_mgmt.create_story
    DEFAULT_BUNDLE.test_mgmt.create_story = lambda epic_id, name: _async_result(sentinel)
    try:
        result = await _dispatch("create_story", {"epic_id": "e1", "name": "Story 1"}, DEFAULT_BUNDLE, is_hosted=False)
    finally:
        DEFAULT_BUNDLE.test_mgmt.create_story = original
    assert result == sentinel


async def test_get_context_includes_mtaf_core_sections():
    # Regression test for the context gap: get_context previously never surfaced API
    # collections/workflows/performance bots, leaving no context-loading path for that domain.
    patches = {
        "user.get_current_user": {"name": "u"},
        "user.list_projects": [],
        "asset.list_websites": [],
        "config.list_environments": [],
        "test_mgmt.list_epics": [],
        "test_mgmt.list_bots": [],
        "test_mgmt.list_suites": [],
        "background.get_queue_status": {},
        "managed_testing.list_api_collections": [{"id": "c1"}],
        "managed_testing.list_workflows": [{"id": "w1"}],
        "managed_testing.list_performance_bots": [{"id": "p1"}],
    }
    originals = {}
    try:
        for path, value in patches.items():
            obj_name, attr = path.split(".")
            obj = getattr(DEFAULT_BUNDLE, obj_name)
            originals[path] = getattr(obj, attr)
            setattr(obj, attr, (lambda v: (lambda: _async_result(v)))(value))
        result = await _get_context(DEFAULT_BUNDLE)
    finally:
        for path, original in originals.items():
            obj_name, attr = path.split(".")
            setattr(getattr(DEFAULT_BUNDLE, obj_name), attr, original)
    assert result["api_collections"] == [{"id": "c1"}]
    assert result["workflows"] == [{"id": "w1"}]
    assert result["performance_bots"] == [{"id": "p1"}]


async def test_get_execution_report_calls_executor_get_execution_results():
    # Regression test for the AttributeError bug: this used to call
    # clients.background.get_execution_report, which never existed.
    sentinel = {"passed": 10, "failed": 0}
    original = DEFAULT_BUNDLE.executor.get_execution_results
    DEFAULT_BUNDLE.executor.get_execution_results = lambda execution_id: _async_result(sentinel)
    try:
        result = await _dispatch("get_execution_report", {"execution_id": "exec-1"}, DEFAULT_BUNDLE, is_hosted=False)
    finally:
        DEFAULT_BUNDLE.executor.get_execution_results = original
    assert result == sentinel


async def test_add_global_parameter_missing_value_rejected_before_client_call():
    def _boom(*a, **kw):
        raise AssertionError("client should never be called when validation fails")

    original = DEFAULT_BUNDLE.config.add_global_parameter
    DEFAULT_BUNDLE.config.add_global_parameter = _boom
    try:
        result = await _dispatch("add_global_parameter", {"name": "admin_email"}, DEFAULT_BUNDLE, is_hosted=False)
    finally:
        DEFAULT_BUNDLE.config.add_global_parameter = original
    assert "error" in result
    assert "value" in result["error"]


async def test_add_global_parameter_dispatches_to_client():
    sentinel = {"globalParameterId": "gp1"}
    original = DEFAULT_BUNDLE.config.add_global_parameter
    DEFAULT_BUNDLE.config.add_global_parameter = lambda name, value, description=None: _async_result(sentinel)
    try:
        result = await _dispatch(
            "add_global_parameter", {"name": "admin_email", "value": "admin@example.com"},
            DEFAULT_BUNDLE, is_hosted=False,
        )
    finally:
        DEFAULT_BUNDLE.config.add_global_parameter = original
    assert result == sentinel


async def test_create_config_vault_secret_dispatches_to_client():
    sentinel = {"id": "secret-1"}
    original = DEFAULT_BUNDLE.config.create_config_vault_secret
    DEFAULT_BUNDLE.config.create_config_vault_secret = lambda name, value, description=None: _async_result(sentinel)
    try:
        result = await _dispatch(
            "create_config_vault_secret", {"name": "db_password", "value": "hunter2"},
            DEFAULT_BUNDLE, is_hosted=False,
        )
    finally:
        DEFAULT_BUNDLE.config.create_config_vault_secret = original
    assert result == sentinel


async def test_update_config_vault_secret_missing_changes_rejected_before_client_call():
    def _boom(*a, **kw):
        raise AssertionError("client should never be called when validation fails")

    original = DEFAULT_BUNDLE.config.update_config_vault_secret
    DEFAULT_BUNDLE.config.update_config_vault_secret = _boom
    try:
        result = await _dispatch("update_config_vault_secret", {"secret_id": "s1"}, DEFAULT_BUNDLE, is_hosted=False)
    finally:
        DEFAULT_BUNDLE.config.update_config_vault_secret = original
    assert "error" in result


async def test_list_global_parameters_and_list_config_vault_secrets_dispatch():
    gp_sentinel = {"customProperties": []}
    vault_sentinel = [{"id": "s1", "name": "db_password"}]
    original_gp = DEFAULT_BUNDLE.config.list_global_parameters
    original_vault = DEFAULT_BUNDLE.config.list_config_vault_secrets
    DEFAULT_BUNDLE.config.list_global_parameters = lambda: _async_result(gp_sentinel)
    DEFAULT_BUNDLE.config.list_config_vault_secrets = lambda: _async_result(vault_sentinel)
    try:
        gp_result = await _dispatch("list_global_parameters", {}, DEFAULT_BUNDLE, is_hosted=False)
        vault_result = await _dispatch("list_config_vault_secrets", {}, DEFAULT_BUNDLE, is_hosted=False)
    finally:
        DEFAULT_BUNDLE.config.list_global_parameters = original_gp
        DEFAULT_BUNDLE.config.list_config_vault_secrets = original_vault
    assert gp_result == gp_sentinel
    assert vault_result == vault_sentinel


# --- Slice 9a: Recorded Script + Common Function ---

async def test_promote_recorded_script_missing_story_id_rejected_before_api_call():
    def _boom(*a, **kw):
        raise AssertionError("client should never be called when validation fails")

    original = DEFAULT_BUNDLE.test_mgmt.promote_recorded_script
    DEFAULT_BUNDLE.test_mgmt.promote_recorded_script = _boom
    try:
        result = await _dispatch(
            "promote_recorded_script", {"recorded_script_id": "rs1"}, DEFAULT_BUNDLE, is_hosted=False
        )
    finally:
        DEFAULT_BUNDLE.test_mgmt.promote_recorded_script = original
    assert "error" in result
    assert "story_id" in result["error"]


async def test_promote_recorded_script_dispatches_with_default_branch():
    captured = {}

    def fake(recorded_script_id, story_id, **kwargs):
        captured["recorded_script_id"] = recorded_script_id
        captured["story_id"] = story_id
        captured.update(kwargs)
        return _async_result({"testScriptId": "ts1"})

    original = DEFAULT_BUNDLE.test_mgmt.promote_recorded_script
    DEFAULT_BUNDLE.test_mgmt.promote_recorded_script = fake
    try:
        result = await _dispatch(
            "promote_recorded_script",
            {"recorded_script_id": "rs1", "story_id": "s1"},
            DEFAULT_BUNDLE, is_hosted=False,
        )
    finally:
        DEFAULT_BUNDLE.test_mgmt.promote_recorded_script = original
    assert result == {"testScriptId": "ts1"}
    assert captured["recorded_script_id"] == "rs1"
    assert captured["story_id"] == "s1"
    assert captured["branch_name"] == "main"


async def test_list_recorded_scripts_dispatches_to_client():
    sentinel = {"content": [{"recordedScriptId": "rs1"}]}
    original = DEFAULT_BUNDLE.test_mgmt.list_recorded_scripts
    DEFAULT_BUNDLE.test_mgmt.list_recorded_scripts = lambda name, branch: _async_result(sentinel)
    try:
        result = await _dispatch("list_recorded_scripts", {}, DEFAULT_BUNDLE, is_hosted=False)
    finally:
        DEFAULT_BUNDLE.test_mgmt.list_recorded_scripts = original
    assert result == sentinel


async def test_create_common_function_missing_return_type_rejected_before_api_call():
    def _boom(*a, **kw):
        raise AssertionError("client should never be called when validation fails")

    original = DEFAULT_BUNDLE.asset.create_common_function
    DEFAULT_BUNDLE.asset.create_common_function = _boom
    try:
        result = await _dispatch(
            "create_common_function",
            {"name": "Login helper", "website_id": "w1", "status": "READY"},
            DEFAULT_BUNDLE, is_hosted=False,
        )
    finally:
        DEFAULT_BUNDLE.asset.create_common_function = original
    assert "error" in result
    assert "return_type" in result["error"]


async def test_create_common_function_invalid_name_rejected_before_api_call():
    def _boom(*a, **kw):
        raise AssertionError("client should never be called when validation fails")

    original = DEFAULT_BUNDLE.asset.create_common_function
    DEFAULT_BUNDLE.asset.create_common_function = _boom
    try:
        result = await _dispatch(
            "create_common_function",
            {"name": "bad_name!", "website_id": "w1", "status": "READY", "return_type": {"type": "String"}},
            DEFAULT_BUNDLE, is_hosted=False,
        )
    finally:
        DEFAULT_BUNDLE.asset.create_common_function = original
    assert "error" in result
    assert "name" in result["error"]


async def test_update_common_function_maps_snake_case_args_to_document_fields():
    captured = {}

    def fake(common_function_id, **changes):
        captured["id"] = common_function_id
        captured["changes"] = changes
        return _async_result({"message": "Success"})

    original = DEFAULT_BUNDLE.asset.update_common_function
    DEFAULT_BUNDLE.asset.update_common_function = fake
    try:
        result = await _dispatch(
            "update_common_function",
            {"common_function_id": "cf1", "name": "New Name", "website_id": "w2", "steps": []},
            DEFAULT_BUNDLE, is_hosted=False,
        )
    finally:
        DEFAULT_BUNDLE.asset.update_common_function = original
    assert result == {"message": "Success"}
    assert captured["id"] == "cf1"
    # snake_case tool args must land as the document's camelCase field names
    assert captured["changes"] == {"name": "New Name", "websiteId": "w2", "testSteps": []}


async def test_update_common_function_with_no_changes_returns_error_without_client_call():
    def _boom(*a, **kw):
        raise AssertionError("client should never be called with an empty change set")

    original = DEFAULT_BUNDLE.asset.update_common_function
    DEFAULT_BUNDLE.asset.update_common_function = _boom
    try:
        result = await _dispatch(
            "update_common_function", {"common_function_id": "cf1"}, DEFAULT_BUNDLE, is_hosted=False
        )
    finally:
        DEFAULT_BUNDLE.asset.update_common_function = original
    assert "error" in result
    assert "at least one field" in result["error"]
