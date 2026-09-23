from pydantic_settings import BaseSettings, SettingsConfigDict

class CoreSettings(BaseSettings):
    core_port: int = 8000
    orchestrator_url: str = "http://localhost:8001"
    provider_timeout: float = 30.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = CoreSettings()
