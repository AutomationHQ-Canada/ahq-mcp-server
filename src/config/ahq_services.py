from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    ahq_base_url: str = "https://app.automationhq.ai"
    ahq_api_token: str
    ahq_org_id: str
    ahq_project_id: str
    llm_api_key: str = ""


# Gateway prefix constants — StripPrefix=1 removes these before forwarding
ASSET_SVC         = "/ahq-asset-services"
TEST_MGMT_SVC     = "/ahq-test-management-services"
BACKGROUND_SVC    = "/ahq-background-v2-services"
CONFIG_SVC        = "/ahq-config-services"
USER_MGMT_SVC     = "/ahq-user-management-services"
EXECUTOR_SVC      = "/ahq-test-bot-executor-services"
LOCAL_EXEC_SVC    = "/test-local-execution-services"
STANDALONE_SVC    = "/ahq-standalone-local-v2-services"
MANAGED_TEST_SVC  = "/managed-testing-service-core"
VIRT_CLIENT_SVC   = "/managed-testing-virtualization-client"
VIRT_SERVER_SVC   = "/managed-testing-virtualization-server"
CDCT_SVC          = "/mtaf-cdct-core"
AUTH_SVC          = "/ahq-auth-services"


settings = Settings()
