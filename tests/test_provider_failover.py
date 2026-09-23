import asyncio
import json

import httpx
import pytest

from apps.orchestrator.workflows import graph
from packages.providers.exceptions import ProviderRateLimitError
from packages.providers.openrouter import OpenRouterProvider
from packages.providers.schemas import ChatRequest, ChatResponse, Message


def request(model: str = "openrouter/free") -> ChatRequest:
    return ChatRequest(
        model=model,
        messages=[Message(role="user", content="hello")],
    )


def test_openrouter_sends_the_model_selected_by_the_client() -> None:
    async def scenario() -> None:
        captured: dict = {}

        def handler(http_request: httpx.Request) -> httpx.Response:
            captured.update(json.loads(http_request.content))
            return httpx.Response(
                200,
                json={
                    "id": "free-response",
                    "model": "openai/a-paid-model",
                    "choices": [{"message": {"content": "ok"}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                },
            )

        provider = OpenRouterProvider(api_key="test-key")
        await provider.client.aclose()
        provider.client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://example.test"
        )
        try:
            response = await provider.complete(request("openai/a-paid-model"))
            assert response.model == "openai/a-paid-model"
            assert captured["model"] == "openai/a-paid-model"
        finally:
            await provider.close()

    asyncio.run(scenario())


def test_openrouter_credit_error_is_classified_for_failover() -> None:
    async def scenario() -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(402, json={"error": {"message": "credits exhausted"}})

        provider = OpenRouterProvider(api_key="test-key")
        await provider.client.aclose()
        provider.client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://example.test"
        )
        try:
            with pytest.raises(ProviderRateLimitError, match="credits exhausted"):
                await provider.complete(request())
        finally:
            await provider.close()

    asyncio.run(scenario())


def test_orchestrator_retries_with_ollama_after_openrouter_failure(monkeypatch) -> None:
    class FailingOpenRouter:
        async def complete(self, _: ChatRequest) -> ChatResponse:
            raise ProviderRateLimitError("credits exhausted", 402)

    class WorkingOllama:
        async def complete(self, local_request: ChatRequest) -> ChatResponse:
            assert local_request.model == "qwen2.5:3b"
            return ChatResponse(
                id="local-response",
                model="qwen2.5:3b",
                content="served locally",
            )

    class FakeModelService:
        def __init__(self) -> None:
            self.primary = FailingOpenRouter()
            self.local = WorkingOllama()
            self.providers = {"openrouter": self.primary, "ollama": self.local}
            self.fallback_model = "qwen2.5:3b"

        async def resolve_provider(self, _: str):
            return self.primary

        def provider_name(self, provider) -> str:
            return "openrouter" if provider is self.primary else "ollama"

        def request_for(self, _: object, chat_request: ChatRequest) -> ChatRequest:
            return chat_request.model_copy(deep=True)

    async def scenario() -> None:
        audit_events: list[dict] = []

        async def log_audit(**kwargs) -> None:
            audit_events.append(kwargs)

        original_service = graph.model_service
        monkeypatch.setattr(graph, "model_service", FakeModelService())
        monkeypatch.setattr(graph.TrackingService, "log_audit", log_audit)
        try:
            result = await graph.execute_node(
                {
                    "request": request(),
                    "request_id": "request-1",
                    "run_id": "run-1",
                    "selected_provider": "openrouter",
                },
                {"configurable": {"session": object()}},
            )
            assert result["selected_provider"] == "ollama"
            assert result["selected_model"] == "qwen2.5:3b"
            assert result["provider_response"].content == "served locally"
            assert audit_events[0]["event_type"] == "provider_fallback"
        finally:
            await original_service.close()

    asyncio.run(scenario())
