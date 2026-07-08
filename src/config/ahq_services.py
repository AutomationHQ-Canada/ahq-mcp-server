from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    ahq_base_url: str = "https://app.automationhq.ai"
    ahq_api_token: str
    # No ahq_org_id here on purpose — org_id is always derived from the token's own
    # organizationId claim (see AhqCredentials.from_settings), never independently configured.
    # A stale/mismatched org_id here would silently write real data into the wrong organization,
    # since the gateway doesn't validate that a request's org-id header matches the token's claim.
    ahq_project_id: str
    llm_api_key: str = ""


# Gateway prefix constants — StripPrefix=1 removes these before forwarding
ASSET_SVC         = "/ahq-asset-services"
TEST_MGMT_SVC     = "/ahq-test-management-services"
BACKGROUND_SVC    = "/ahq-background-v2-services"
CONFIG_SVC        = "/ahq-config-services"
USER_MGMT_SVC     = "/ahq-user-management-services"
EXECUTOR_SVC      = "/ahq-test-bot-executor-services"
LOCAL_EXEC_SVC    = "/test-local-execution-services"  # NOT gateway-routed — runs on the user's machine, see local_exec_client.py
STANDALONE_SVC    = "/ahq-standalone-local-v2-services"
MANAGED_TEST_SVC  = "/mtaf-core"          # gateway route id, NOT the repo name "managed-testing-service-core"
VIRT_CLIENT_SVC   = "/mtaf-sv-client"     # gateway route id, NOT the repo name "managed-testing-virtualization-client"
VIRT_SERVER_SVC   = "/mtaf-sv-server"     # gateway route id, NOT the repo name "managed-testing-virtualization-server"
CDCT_SVC          = "/mtaf-cdct"          # gateway route id, NOT the repo name "mtaf-cdct-core"
AUTH_SVC          = "/ahq-auth-services"
EMAIL_SVC         = "/ahq-email-v2-services"


settings = Settings()
