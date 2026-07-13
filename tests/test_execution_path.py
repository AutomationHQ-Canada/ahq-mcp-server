"""
Execution-path slice: create_test_bot / suite fixes / execute_bot / lookups.
Contracts from TestBotController.addTestBot, TestBotExecutionController.executeBot,
TestSuiteController (no /scripts endpoint — embedded testScripts), and
automationhq-frontend-v2's TestBotSchema + ExecutionConfigurationSchema (zod).
"""
import pytest
from pydantic import ValidationError

from src.clients.executor_client import ExecutorClient
from src.clients.test_mgmt_client import TestMgmtClient
from src.schema.asset_kinds import ExecuteBotArgs, TestBotCreateArgs


# --- validators ---

def _valid_exec_config(**overrides):
    cfg = {"baseUrl": "env-uuid-1", "browser": "Chrome", "gridId": "grid-1",
           "browserVersion": "latest", "osType": "Grid OS"}
    cfg.update(overrides)
    return cfg


def test_execute_bot_args_accepts_minimal_valid_config():
    args = ExecuteBotArgs(bot_id="b1", execution_configuration=_valid_exec_config())
    assert args.execution_configuration.timeout == 60          # form default
    assert args.execution_configuration.waitForElementTimeout == 30
    assert args.execution_configuration.screenshotOnError is True


@pytest.mark.parametrize("missing", ["baseUrl", "browser", "gridId", "browserVersion", "osType"])
def test_execute_bot_args_rejects_missing_required(missing):
    cfg = _valid_exec_config()
    del cfg[missing]
    with pytest.raises(ValidationError):
        ExecuteBotArgs(bot_id="b1", execution_configuration=cfg)


def test_execute_bot_args_rejects_raw_url_as_base_url():
    # baseUrl is an ENVIRONMENT ID server-side; a raw URL survives enqueue and then kills the
    # run at report time with "Environment not found for this id" (found live 2026-07-13).
    with pytest.raises(ValidationError) as exc_info:
        ExecuteBotArgs(bot_id="b1",
                       execution_configuration=_valid_exec_config(baseUrl="https://app.example.com"))
    assert "Environment ID" in str(exc_info.value)


@pytest.mark.parametrize("field,value", [
    ("timeout", 0), ("timeout", 301),
    ("waitForElementTimeout", 0), ("waitForElementTimeout", 301),
    ("delayBetweenSteps", 31), ("numberOfRetries", 4),
])
def test_execute_bot_args_enforces_form_bounds(field, value):
    with pytest.raises(ValidationError):
        ExecuteBotArgs(bot_id="b1", execution_configuration=_valid_exec_config(**{field: value}))


def test_test_bot_create_args_requires_at_least_one_suite():
    with pytest.raises(ValidationError):
        TestBotCreateArgs(name="Bot", test_suites=[])
    TestBotCreateArgs(name="Bot", test_suites=[{"testSuiteId": "s1", "name": "Suite"}])


def test_test_bot_create_args_name_bounds():
    with pytest.raises(ValidationError):
        TestBotCreateArgs(name="", test_suites=[{"testSuiteId": "s1"}])
    with pytest.raises(ValidationError):
        TestBotCreateArgs(name="x" * 121, test_suites=[{"testSuiteId": "s1"}])


# --- client wiring ---

async def test_create_test_bot_body_shape(monkeypatch):
    client = TestMgmtClient()
    captured = {}

    async def fake_post(path, json=None, **kwargs):
        captured["path"] = path
        captured["json"] = json
        return {"id": "bot-1"}

    monkeypatch.setattr(client, "post", fake_post)
    await client.create_test_bot("My Bot", [{"testSuiteId": "s1", "name": "Suite"}])

    assert captured["path"] == "/rest/api/testbots"
    assert captured["json"]["name"] == "My Bot"
    assert captured["json"]["testSuites"] == [{"testSuiteId": "s1", "name": "Suite"}]
    assert "botType" not in captured["json"]  # server defaults to REGRESSION_TEST


async def test_add_scripts_to_suite_is_get_merge_put(monkeypatch):
    client = TestMgmtClient()
    calls = []

    async def fake_get_suite(suite_id):
        return {"testSuiteId": suite_id, "name": "S",
                "testScripts": [{"testScriptId": "old", "sequence": 1}]}

    async def fake_get_script(script_id):
        return {"testScriptId": script_id, "name": f"Script {script_id}", "status": "Ready"}

    async def fake_put(path, json=None, **kwargs):
        calls.append((path, json))
        return {"ok": True}

    monkeypatch.setattr(client, "get_suite", fake_get_suite)
    monkeypatch.setattr(client, "get_test_script", fake_get_script)
    monkeypatch.setattr(client, "put", fake_put)

    await client.add_scripts_to_suite("suite-1", ["new-1", "old"])  # "old" already attached

    path, body = calls[0]
    assert path == "/rest/api/suites/suite-1"
    ids = [s["testScriptId"] for s in body["testScripts"]]
    assert ids == ["old", "new-1"]              # merged, no duplicate of "old"
    assert body["testScripts"][1]["sequence"] == 2


async def test_execute_bot_sends_full_botexecution_body(monkeypatch):
    client = ExecutorClient()
    captured = {}

    async def fake_post(path, json=None, params=None, **kwargs):
        captured.update(path=path, json=json, params=params)
        return {"executionId": "e1"}

    monkeypatch.setattr(client, "post", fake_post)
    await client.execute_bot("bot-1", {"baseUrl": "u", "browser": "Chrome", "gridId": "g"},
                             name="Run 1", profile_id="p1")

    assert captured["path"] == "/rest/api/bots/bot-1/execute"
    assert captured["json"]["name"] == "Run 1"
    assert captured["json"]["profileId"] == "p1"
    assert captured["json"]["executionConfiguration"]["gridId"] == "g"
    assert captured["params"] is None  # partialExecution only sent when requested


async def test_get_execution_results_uses_detailed_results_path(monkeypatch):
    client = ExecutorClient()
    captured = {}

    async def fake_get(path, **kwargs):
        captured["path"] = path
        return {}

    monkeypatch.setattr(client, "get", fake_get)
    await client.get_execution_results("e1")
    assert captured["path"] == "/rest/api/bots/execution/e1/detailed-results"
