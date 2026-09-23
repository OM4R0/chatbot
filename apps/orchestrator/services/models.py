import logging
from typing import Dict, List

from apps.orchestrator.config import settings
from packages.providers.base import AIProvider
from packages.providers.ollama import OllamaProvider
from packages.providers.openrouter import OpenRouterProvider
from packages.providers.schemas import ChatRequest, ProviderModel

logger = logging.getLogger(__name__)


class ModelService:
    """Own provider clients and select a safe, deterministic execution path."""

    def __init__(self) -> None:
        self.providers: Dict[str, AIProvider] = {}
        if settings.openrouter_api_key.strip():
            self.providers["openrouter"] = OpenRouterProvider(
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
                timeout=settings.provider_timeout,
            )

        # Ollama stays available even when an OpenRouter key is not configured.
        # It is the automatic local failover path.
        self.providers["ollama"] = OllamaProvider(
            base_url=settings.ollama_base_url,
            timeout=max(settings.provider_timeout, 120.0),
        )
        self.fallback_model = settings.default_fallback_model
        self.openrouter_model = settings.default_openrouter_model

    async def get_all_models(self) -> List[ProviderModel]:
        """Return every model available from configured providers."""
        all_models: List[ProviderModel] = []
        seen: set[str] = set()
        for provider_name, provider in self.providers.items():
            try:
                models = await provider.list_models()
            except Exception as exc:  # A degraded provider must not hide the other one.
                logger.warning("Could not fetch %s models: %s", provider_name, exc)
                continue

            for model in models:
                if model.id not in seen:
                    all_models.append(model)
                    seen.add(model.id)
        return all_models

    async def resolve_provider(self, requested_model: str) -> AIProvider:
        """Select a provider without a model-list network round trip.

        OpenRouter ids contain a slash. Simple ids are assumed to be local
        Ollama tags. If OpenRouter is unavailable, ``request_for`` replaces a
        remote model ID with the configured local fallback before invocation.
        """
        wants_openrouter = requested_model == self.openrouter_model or "/" in requested_model
        if wants_openrouter and "openrouter" in self.providers:
            return self.providers["openrouter"]
        if "ollama" in self.providers:
            return self.providers["ollama"]
        if "openrouter" in self.providers:
            return self.providers["openrouter"]
        raise ValueError("No AI provider is configured.")

    def provider_name(self, provider: AIProvider) -> str:
        for name, candidate in self.providers.items():
            if candidate is provider:
                return name
        return "unknown"

    def request_for(self, provider: AIProvider, request: ChatRequest) -> ChatRequest:
        """Return a provider-safe copy of a user request.

        If OpenRouter is unavailable, a remote model id such as
        ``openrouter/free`` cannot be sent to Ollama. It is replaced by the
        configured local model before the fallback call starts.
        """
        prepared = request.model_copy(deep=True)
        provider_name = self.provider_name(provider)
        if provider_name == "ollama" and (
            prepared.model == self.openrouter_model or "/" in prepared.model
        ):
            prepared.model = self.fallback_model
        return prepared

    async def close(self) -> None:
        for provider in self.providers.values():
            await provider.close()


model_service = ModelService()
