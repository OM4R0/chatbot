from pydantic_settings import BaseSettings, SettingsConfigDict

class CoreSettings(BaseSettings):
    core_port: int = 8000
    orchestrator_url: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = CoreSettings()
