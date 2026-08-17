from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    service_api_key: str = "dev-key"

    gemini_api_key: str = ""
    llm_model: str = "gemini-2.0-flash"
    llm_max_tokens: int = 500
    llm_temperature: float = 0.4
    llm_timeout_seconds: int = 15

    frontend_origin: str = "http://localhost:5173"


settings = Settings()