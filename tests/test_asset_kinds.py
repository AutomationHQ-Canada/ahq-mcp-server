import pytest
from pydantic import ValidationError

from src.schema.asset_kinds import (
    AddGlobalParameterArgs,
    AddScriptsToSuiteArgs,
    ApiCollectionCreateArgs,
    ApiRequestCreateArgs,
    CommonFunctionCreateArgs,
    CommonFunctionUpdateArgs,
    CreateConfigVaultSecretArgs,
    PromoteRecordedScriptArgs,
    EpicCreateArgs,
    SchedulerCreateArgs,
    StoryCreateArgs,
    SuiteCreateArgs,
    TestScriptCreateArgs,
    UpdateConfigVaultSecretArgs,
    WorkflowCreateArgs,
    format_validation_error,
)

VALID_STEP = {"templateId": "real-uuid-1234", "parameters": []}
VALID_EXEC_CONFIG = {
    "baseUrl": "env-uuid-1", "browser": "chrome", "gridId": "grid-1",
    "browserVersion": "latest", "osType": "Grid OS",
}


def _valid_test_script_args(**overrides):
    args = dict(name="A script", steps=[VALID_STEP], website_id="w1", story_id="s1")
    args.update(overrides)
    return args


class TestTestScriptCreateArgs:
    def test_accepts_all_required_fields(self):
        TestScriptCreateArgs(**_valid_test_script_args())

    def test_rejects_missing_story_id(self):
        args = _valid_test_script_args()
        del args["story_id"]
        with pytest.raises(ValidationError):
            TestScriptCreateArgs(**args)

    def test_rejects_missing_website_id(self):
        args = _valid_test_script_args()
        del args["website_id"]
        with pytest.raises(ValidationError):
            TestScriptCreateArgs(**args)

    def test_rejects_empty_steps(self):
        with pytest.raises(ValidationError):
            TestScriptCreateArgs(**_valid_test_script_args(steps=[]))

    def test_rejects_invalid_status(self):
        with pytest.raises(ValidationError):
            TestScriptCreateArgs(**_valid_test_script_args(status="Bogus"))

    def test_built_in_template_missing_title_rejected(self):
        step = {"templateId": "template-id-3"}
        with pytest.raises(ValidationError):
            TestScriptCreateArgs(**_valid_test_script_args(steps=[step]))

    def test_built_in_template_with_title_accepted(self):
        step = {"templateId": "template-id-3", "templateTitle": "Enter {{text}}"}
        TestScriptCreateArgs(**_valid_test_script_args(steps=[step]))

    def test_common_function_template_without_title_accepted(self):
        # real UUID templateIds (Common Functions) don't need templateTitle
        TestScriptCreateArgs(**_valid_test_script_args(steps=[VALID_STEP]))

    def test_repair_comment_required_when_to_be_repaired(self):
        with pytest.raises(ValidationError):
            TestScriptCreateArgs(**_valid_test_script_args(status="To Be Repaired"))

    def test_repair_comment_satisfies_to_be_repaired(self):
        TestScriptCreateArgs(**_valid_test_script_args(status="To Be Repaired", repair_comment="fix locator"))

    def test_extra_keys_ignored(self):
        # page_id/branch_name/script_type are real tool args this validator doesn't care about
        TestScriptCreateArgs(**_valid_test_script_args(page_id="p1", branch_name="main", script_type="WEB"))


class TestSuiteAndScripts:
    def test_suite_create_requires_name(self):
        SuiteCreateArgs(name="My Suite")
        with pytest.raises(ValidationError):
            SuiteCreateArgs()

    def test_add_scripts_to_suite_requires_nonempty_ids(self):
        AddScriptsToSuiteArgs(suite_id="s1", script_ids=["a"])
        with pytest.raises(ValidationError):
            AddScriptsToSuiteArgs(suite_id="s1", script_ids=[])


class TestScheduler:
    def test_recurring_accepts_all_required_fields(self):
        SchedulerCreateArgs(bot_id="b1", name="Nightly Run", cron="0 0 * * *",
                            execution_configuration=VALID_EXEC_CONFIG)

    def test_recurring_emails_optional_defaults_empty(self):
        args = SchedulerCreateArgs(bot_id="b1", name="Nightly Run", cron="0 0 * * *",
                                   execution_configuration=VALID_EXEC_CONFIG)
        assert args.emails == []

    def test_recurring_rejects_missing_name(self):
        with pytest.raises(ValidationError):
            SchedulerCreateArgs(bot_id="b1", cron="0 0 * * *", execution_configuration=VALID_EXEC_CONFIG)

    def test_recurring_rejects_blank_name(self):
        with pytest.raises(ValidationError):
            SchedulerCreateArgs(bot_id="b1", name="", cron="0 0 * * *", execution_configuration=VALID_EXEC_CONFIG)

    def test_recurring_rejects_name_over_120_chars(self):
        with pytest.raises(ValidationError):
            SchedulerCreateArgs(bot_id="b1", name="x" * 121, cron="0 0 * * *",
                               execution_configuration=VALID_EXEC_CONFIG)

    def test_recurring_rejects_missing_cron(self):
        with pytest.raises(ValidationError):
            SchedulerCreateArgs(bot_id="b1", name="Nightly Run", execution_configuration=VALID_EXEC_CONFIG)

    def test_recurring_rejects_blank_cron(self):
        # This is the exact case that NullPointerExceptions server-side (recurringRule.replace on
        # a null/blank value) — catching it here means the caller gets a clean error instead.
        with pytest.raises(ValidationError):
            SchedulerCreateArgs(bot_id="b1", name="Nightly Run", cron="", execution_configuration=VALID_EXEC_CONFIG)

    def test_recurring_rejects_execution_configuration_missing_browser(self):
        with pytest.raises(ValidationError):
            SchedulerCreateArgs(
                bot_id="b1", name="Nightly Run", cron="0 0 * * *",
                execution_configuration={"gridUrlForExecution": "https://grid.example.com"},
            )


class TestApiAndWorkflow:
    def test_api_collection_requires_name(self):
        ApiCollectionCreateArgs(name="Collection")
        with pytest.raises(ValidationError):
            ApiCollectionCreateArgs()

    def test_api_request_rejects_bad_method(self):
        with pytest.raises(ValidationError):
            ApiRequestCreateArgs(name="Req", method="FETCH", url="https://x.com")

    def test_api_request_accepts_valid_method(self):
        ApiRequestCreateArgs(name="Req", method="GET", url="https://x.com")

    def test_workflow_rejects_empty_workflow_list(self):
        with pytest.raises(ValidationError):
            WorkflowCreateArgs(name="Flow", workflow_list=[])

    def test_workflow_accepts_nonempty_workflow_list(self):
        WorkflowCreateArgs(name="Flow", workflow_list=[{"apiRequestV2Id": "r1"}])


class TestEpicStory:
    def test_epic_requires_name(self):
        EpicCreateArgs(name="Epic 1")
        with pytest.raises(ValidationError):
            EpicCreateArgs()

    def test_story_requires_epic_id_and_name(self):
        StoryCreateArgs(epic_id="e1", name="Story 1")
        with pytest.raises(ValidationError):
            StoryCreateArgs(name="Story 1")


class TestGlobalParametersAndVault:
    def test_add_global_parameter_requires_name_and_value(self):
        AddGlobalParameterArgs(name="admin_email", value="admin@example.com")
        with pytest.raises(ValidationError):
            AddGlobalParameterArgs(value="admin@example.com")
        with pytest.raises(ValidationError):
            AddGlobalParameterArgs(name="admin_email")

    def test_create_config_vault_secret_requires_name_and_value(self):
        CreateConfigVaultSecretArgs(name="db_password", value="hunter2")
        with pytest.raises(ValidationError):
            CreateConfigVaultSecretArgs(name="db_password")

    def test_update_config_vault_secret_requires_secret_id(self):
        with pytest.raises(ValidationError):
            UpdateConfigVaultSecretArgs(value="new-value")

    def test_update_config_vault_secret_requires_at_least_one_change(self):
        with pytest.raises(ValidationError):
            UpdateConfigVaultSecretArgs(secret_id="s1")

    def test_update_config_vault_secret_accepts_value_only_or_description_only(self):
        UpdateConfigVaultSecretArgs(secret_id="s1", value="new-value")
        UpdateConfigVaultSecretArgs(secret_id="s1", description="new description")


def test_format_validation_error_is_readable():
    try:
        TestScriptCreateArgs(**{"name": "x", "steps": [VALID_STEP]})
    except ValidationError as e:
        message = format_validation_error("create_test_script", e)
        assert "create_test_script" in message
        assert "website_id" in message
        assert "story_id" in message


class TestPromoteRecordedScriptArgs:
    def test_accepts_required_ids(self):
        PromoteRecordedScriptArgs(recorded_script_id="rs1", story_id="s1")

    def test_rejects_missing_story_id(self):
        with pytest.raises(ValidationError):
            PromoteRecordedScriptArgs(recorded_script_id="rs1")

    def test_rejects_blank_story_id(self):
        with pytest.raises(ValidationError):
            PromoteRecordedScriptArgs(recorded_script_id="rs1", story_id="   ")

    def test_ignores_optional_extras(self):
        PromoteRecordedScriptArgs(recorded_script_id="rs1", story_id="s1", name="X", branch_name="main")


def _valid_common_function_args(**overrides):
    args = dict(
        name="Login helper",
        website_id="w1",
        status="READY",
        return_type={"type": "String"},
    )
    args.update(overrides)
    return args


class TestCommonFunctionCreateArgs:
    def test_accepts_all_required_fields(self):
        CommonFunctionCreateArgs(**_valid_common_function_args())

    def test_rejects_missing_website_id(self):
        args = _valid_common_function_args()
        del args["website_id"]
        with pytest.raises(ValidationError):
            CommonFunctionCreateArgs(**args)

    def test_rejects_missing_return_type(self):
        args = _valid_common_function_args()
        del args["return_type"]
        with pytest.raises(ValidationError):
            CommonFunctionCreateArgs(**args)

    def test_rejects_return_type_with_blank_type(self):
        with pytest.raises(ValidationError):
            CommonFunctionCreateArgs(**_valid_common_function_args(return_type={"type": "  "}))

    def test_return_type_name_defaults_empty(self):
        # ReturnTypeSchema in the frontend allows an empty name with type present
        CommonFunctionCreateArgs(**_valid_common_function_args(return_type={"type": "String", "array": True}))

    def test_rejects_name_with_special_characters(self):
        # Frontend regex: ^[A-Za-z0-9\s-]+$ — underscores/punctuation are rejected by the real form
        with pytest.raises(ValidationError):
            CommonFunctionCreateArgs(**_valid_common_function_args(name="login_helper!"))

    def test_rejects_name_over_120_chars(self):
        with pytest.raises(ValidationError):
            CommonFunctionCreateArgs(**_valid_common_function_args(name="a" * 121))

    def test_rejects_description_over_600_chars(self):
        with pytest.raises(ValidationError):
            CommonFunctionCreateArgs(**_valid_common_function_args(description="d" * 601))


class TestCommonFunctionUpdateArgs:
    def test_accepts_id_only(self):
        # Presence of at least one change is checked in _dispatch (it needs the raw args dict);
        # the validator itself only guards field formats.
        CommonFunctionUpdateArgs(common_function_id="cf1")

    def test_accepts_rename(self):
        CommonFunctionUpdateArgs(common_function_id="cf1", name="New Name")

    def test_rejects_invalid_new_name(self):
        with pytest.raises(ValidationError):
            CommonFunctionUpdateArgs(common_function_id="cf1", name="bad@name")

    def test_rejects_missing_id(self):
        with pytest.raises(ValidationError):
            CommonFunctionUpdateArgs(name="New Name")
