from src.mcp_server import _dispatch, _HOSTED_UNSUPPORTED, DEFAULT_BUNDLE


async def test_hosted_unsupported_tools_return_clean_error_when_hosted():
    for name in _HOSTED_UNSUPPORTED:
        result = await _dispatch(name, {}, DEFAULT_BUNDLE, is_hosted=True)
        assert "error" in result
        assert "not available over the hosted MCP server" in result["error"]


async def test_check_local_agent_status_guard_does_not_fire_when_not_hosted():
    # is_hosted=False (stdio) must NOT be short-circuited — it should reach the real client call.
    # get_agent_status() itself fails soft (returns {"online": False, ...}) rather than raising,
    # so this proves the guard was skipped without needing a live local agent.
    result = await _dispatch("check_local_agent_status", {}, DEFAULT_BUNDLE, is_hosted=False)
    assert result == {"online": False, "error": "Local agent not running at localhost:9202"}


async def test_unknown_tool_returns_error():
    result = await _dispatch("not_a_real_tool", {}, DEFAULT_BUNDLE, is_hosted=False)
    assert result == {"error": "Unknown tool: not_a_real_tool"}
