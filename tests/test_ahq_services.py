from src.config.ahq_services import Settings


def test_gw_prefix_defaults_match_saas_gateway_convention():
    # No AHQ_GW_PREFIX_* env vars set -> every prefix must equal today's hardcoded SaaS value,
    # so existing dev/prod behavior is provably unchanged by this setting existing at all.
    s = Settings(_env_file=None)

    assert s.ahq_gw_prefix_asset == "/ahq-asset-services"
    assert s.ahq_gw_prefix_test_mgmt == "/ahq-test-management-services"
    assert s.ahq_gw_prefix_background == "/ahq-background-v2-services"
    assert s.ahq_gw_prefix_config == "/ahq-config-services"
    assert s.ahq_gw_prefix_user_mgmt == "/ahq-user-management-services"
    assert s.ahq_gw_prefix_executor == "/ahq-test-bot-executor-services"
    assert s.ahq_gw_prefix_standalone == "/ahq-standalone-local-v2-services"
    assert s.ahq_gw_prefix_managed_test == "/mtaf-core"
    assert s.ahq_gw_prefix_virt_client == "/mtaf-sv-client"
    assert s.ahq_gw_prefix_virt_server == "/mtaf-sv-server"
    assert s.ahq_gw_prefix_cdct == "/mtaf-cdct"
    assert s.ahq_gw_prefix_auth == "/ahq-auth-services"
    assert s.ahq_gw_prefix_email == "/ahq-email-v2-services"


def test_gw_prefix_overrides_match_aviso_gateway_route_table():
    # A self-hosted deployment target (e.g. Aviso) whose gateway uses a different route-id
    # convention overrides only the prefixes it needs, via plain env vars/config — no code
    # change. Values here match Aviso's confirmed live application-aviso.yml route table.
    s = Settings(
        _env_file=None,
        ahq_gw_prefix_asset="/ca-utap-asset-svc",
        ahq_gw_prefix_test_mgmt="/ca-utap-test-management-svc",
        ahq_gw_prefix_background="/ca-utap-background-v2-svc",
        ahq_gw_prefix_config="/ca-utap-config-svc",
        ahq_gw_prefix_user_mgmt="/ca-utap-user-management-svc",
        ahq_gw_prefix_executor="/ca-utap-test-bot-executor-svc",
        ahq_gw_prefix_standalone="/ca-utap-standalone-local-v2-svc",
        ahq_gw_prefix_managed_test="/ca-mtaf-core",
        ahq_gw_prefix_virt_client="/ca-mtaf-sv-client",
        ahq_gw_prefix_virt_server="/ca-mtaf-sv-server",
        ahq_gw_prefix_cdct="/ca-mtaf-cdct",
        ahq_gw_prefix_auth="/ca-utap-auth-svc",
        ahq_gw_prefix_email="/ca-utap-email-v2-svc",
    )

    assert s.ahq_gw_prefix_asset == "/ca-utap-asset-svc"
    assert s.ahq_gw_prefix_test_mgmt == "/ca-utap-test-management-svc"
    assert s.ahq_gw_prefix_background == "/ca-utap-background-v2-svc"
    assert s.ahq_gw_prefix_config == "/ca-utap-config-svc"
    assert s.ahq_gw_prefix_user_mgmt == "/ca-utap-user-management-svc"
    assert s.ahq_gw_prefix_executor == "/ca-utap-test-bot-executor-svc"
    assert s.ahq_gw_prefix_standalone == "/ca-utap-standalone-local-v2-svc"
    assert s.ahq_gw_prefix_managed_test == "/ca-mtaf-core"
    assert s.ahq_gw_prefix_virt_client == "/ca-mtaf-sv-client"
    assert s.ahq_gw_prefix_virt_server == "/ca-mtaf-sv-server"
    assert s.ahq_gw_prefix_cdct == "/ca-mtaf-cdct"
    assert s.ahq_gw_prefix_auth == "/ca-utap-auth-svc"
    assert s.ahq_gw_prefix_email == "/ca-utap-email-v2-svc"


def test_module_level_svc_constants_derive_from_default_settings():
    # The module-level constants every client under src/clients/ imports (e.g. `from
    # src.config.ahq_services import ASSET_SVC`) must still resolve to today's SaaS values in
    # the actual running process, since ahq_services.settings is built from real env/dotenv.
    from src.config import ahq_services

    assert ahq_services.ASSET_SVC == ahq_services.settings.ahq_gw_prefix_asset
    assert ahq_services.TEST_MGMT_SVC == ahq_services.settings.ahq_gw_prefix_test_mgmt
    assert ahq_services.LOCAL_EXEC_SVC == "/test-local-execution-services"


def test_credentials_accept_both_the_testbots_and_ahq_variable_names(monkeypatch, tmp_path):
    """The rebrand must not strand an existing .env.

    A renamed variable fails silently: the token reads as empty, which surfaces as "not
    configured" and looks like a broken install rather than a renamed setting. Both spellings
    resolve, and the TestBots one wins when both are present.
    """
    for var in ("AHQ_API_TOKEN", "AHQ_PROJECT_ID", "AHQ_BASE_URL",
                "TESTBOTS_API_TOKEN", "TESTBOTS_PROJECT_ID", "TESTBOTS_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    # An empty env_file, or a real ~/.ahq/.env on the dev machine masks the result.
    empty = tmp_path / "empty.env"
    empty.write_text("")

    def settings() -> Settings:
        return Settings(_env_file=str(empty))

    monkeypatch.setenv("AHQ_API_TOKEN", "legacy-token")
    monkeypatch.setenv("AHQ_PROJECT_ID", "legacy-project")
    monkeypatch.setenv("AHQ_BASE_URL", "https://legacy.example")
    s = settings()
    assert (s.ahq_api_token, s.ahq_project_id, s.ahq_base_url) == (
        "legacy-token", "legacy-project", "https://legacy.example")

    monkeypatch.setenv("TESTBOTS_API_TOKEN", "current-token")
    monkeypatch.setenv("TESTBOTS_PROJECT_ID", "current-project")
    monkeypatch.setenv("TESTBOTS_BASE_URL", "https://current.example")
    s = settings()
    assert (s.ahq_api_token, s.ahq_project_id, s.ahq_base_url) == (
        "current-token", "current-project", "https://current.example")


def test_both_credential_homes_are_searched_with_testbots_taking_precedence():
    """~/.ahq/.env keeps working; ~/.testbots/.env wins if a user creates it."""
    from src.config.ahq_services import _env_file_candidates

    candidates = _env_file_candidates()
    ahq = next(i for i, c in enumerate(candidates) if c.endswith(r".ahq\.env")
               or c.endswith(".ahq/.env"))
    testbots = next(i for i, c in enumerate(candidates) if c.endswith(r".testbots\.env")
                    or c.endswith(".testbots/.env"))
    # pydantic-settings: later files win.
    assert ahq < testbots
