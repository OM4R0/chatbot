from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    
    # AI Providers Settings
    openrouter_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    
    # Model Selection Settings (Fallback mechanism)
    default_fallback_model: str = "llama3" # Default Ollama model if OpenRouter fails

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()