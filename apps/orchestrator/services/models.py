from typing import List, Dict
from packages.providers.base import AIProvider
from packages.providers.openrouter import OpenRouterProvider
from packages.providers.ollama import OllamaProvider
from packages.providers.schemas import ProviderModel
from apps.orchestrator.config import settings

class ModelService:
    def __init__(self):
        # Initialize providers using settings (Dependency Injection)
        self.providers: Dict[str, AIProvider] = {}
        
        # Only add OpenRouter if API key is provided
        if settings.openrouter_api_key:
            self.providers["openrouter"] = OpenRouterProvider(
                api_key=settings.openrouter_api_key
            )
            
        # Ollama is always added (local fallback)
        self.providers["ollama"] = OllamaProvider(
            base_url=settings.ollama_base_url
        )
        
        self.fallback_model = settings.default_fallback_model

    async def get_all_models(self) -> List[ProviderModel]:
        """Fetch and combine models from all enabled providers (Task 17)."""
        all_models = []
        for provider_name, provider in self.providers.items():
            try:
                models = await provider.list_models()
                all_models.extend(models)
            except Exception as e:
                # Log error but continue fetching from other providers
                print(f"Error fetching models from {provider_name}: {e}")
        return all_models

    async def resolve_provider(self, requested_model: str) -> AIProvider:
        """
        Determine which provider owns the requested model (Task 18).
        Falls back to the default configured model if not found.
        """
        models = await self.get_all_models()
        
        # 1. Try to find the exact requested model
        for model in models:
            if model.id == requested_model:
                return self.providers.get(model.owned_by)
                
        # 2. If not found, use the fallback mechanism
        print(f"Model '{requested_model}' not found. Falling back to '{self.fallback_model}'.")
        for model in models:
            if model.id == self.fallback_model:
                return self.providers.get(model.owned_by)
                
        # 3. If fallback also fails
        raise ValueError(f"Requested model and fallback model '{self.fallback_model}' are unavailable.")

# Create a singleton instance to be used across the app
model_service = ModelService()