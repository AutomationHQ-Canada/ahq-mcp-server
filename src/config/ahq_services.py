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


settings = Settings()
