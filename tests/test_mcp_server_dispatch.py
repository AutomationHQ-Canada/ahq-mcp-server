from src.mcp_server import _dispatch, _HOSTED_UNSUPPORTED, DEFAULT_BUNDLE


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
