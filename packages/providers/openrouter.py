import json
import uuid
from typing import List, AsyncGenerator

import httpx

from .base import AIProvider
from .schemas import ChatRequest, ChatResponse, ProviderModel
from .exceptions import (
    ProviderAPIError,
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)

class OpenRouterProvider(AIProvider):
    """OpenRouter client that forwards the model selected by the user."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: float = 30.0,
    ):
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            timeout=httpx.Timeout(timeout)
        )

    def _request_payload(self, request: ChatRequest, stream: bool) -> dict:
        payload = request.model_dump()
        payload["stream"] = stream
        return payload

    @staticmethod
    def _api_error(response: httpx.Response) -> ProviderAPIError:
        try:
            detail = response.json().get("error", {}).get("message")
        except (ValueError, AttributeError):
            detail = None
        detail = detail or response.text or response.reason_phrase
        message = f"OpenRouter API error ({response.status_code}): {detail}"
        if response.status_code in {401, 403}:
            return ProviderAuthenticationError(message, response.status_code)
        if response.status_code in {402, 408, 429}:
            return ProviderRateLimitError(message, response.status_code)
        return ProviderAPIError(message, response.status_code)

    async def list_models(self) -> List[ProviderModel]:
        try:
            response = await self.client.get("/models")
            if response.is_error:
                raise self._api_error(response)
            data = response.json()
            models = []
            seen = set()
            for model in data.get("data", []):
                model_id = model.get("id")
                if model_id and model_id not in seen:
                    models.append(ProviderModel(id=model_id, owned_by="openrouter"))
                    seen.add(model_id)
            return models
        except httpx.TimeoutException:
            raise ProviderTimeoutError("OpenRouter timeout fetching models.")
        except httpx.RequestError as e:
            raise ProviderConnectionError(f"OpenRouter connection error: {e}")

    async def complete(self, request: ChatRequest) -> ChatResponse:
        payload = self._request_payload(request, stream=False)
        try:
            response = await self.client.post("/chat/completions", json=payload)
            if response.is_error:
                raise self._api_error(response)
            data = response.json()

            return ChatResponse(
                id=data.get("id", str(uuid.uuid4())),
                model=data.get("model", payload["model"]),
                content=data["choices"][0]["message"].get("content", ""),
                prompt_tokens=data.get("usage", {}).get("prompt_tokens", 0),
                completion_tokens=data.get("usage", {}).get("completion_tokens", 0)
            )
        except httpx.TimeoutException:
            raise ProviderTimeoutError("OpenRouter timeout during completion.")
        except httpx.RequestError as e:
            raise ProviderConnectionError(f"OpenRouter connection error: {e}")

    async def stream(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        payload = self._request_payload(request, stream=True)
        try:
            async with self.client.stream("POST", "/chat/completions", json=payload) as response:
                if response.is_error:
                    await response.aread()
                    raise self._api_error(response)
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        chunk = json.loads(line[6:])
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        if "content" in delta:
                            yield delta["content"]
        except httpx.TimeoutException:
            raise ProviderTimeoutError("OpenRouter timeout during stream.")
        except httpx.RequestError as e:
            raise ProviderConnectionError(f"OpenRouter connection error: {e}")

    async def close(self):
        await self.client.aclose()
