import httpx
import json
import uuid
from typing import List, AsyncGenerator

from .base import AIProvider
from .schemas import ChatRequest, ChatResponse, ProviderModel
from .exceptions import ProviderConnectionError, ProviderTimeoutError, ProviderError

class OpenRouterProvider(AIProvider):
    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1"):
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            timeout=httpx.Timeout(60.0)
        )

    async def list_models(self) -> List[ProviderModel]:
        try:
            response = await self.client.get("/models")
            response.raise_for_status()
            data = response.json()
            return [
                ProviderModel(id=m["id"], owned_by="openrouter") 
                for m in data.get("data", [])
            ]
        except httpx.TimeoutException:
            raise ProviderTimeoutError("OpenRouter timeout fetching models.")
        except httpx.RequestError as e:
            raise ProviderConnectionError(f"OpenRouter connection error: {e}")

    async def complete(self, request: ChatRequest) -> ChatResponse:
        payload = request.model_dump()
        payload["stream"] = False
        
        try:
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            
            return ChatResponse(
                id=data.get("id", str(uuid.uuid4())),
                model=data["model"],
                content=data["choices"][0]["message"]["content"],
                prompt_tokens=data.get("usage", {}).get("prompt_tokens", 0),
                completion_tokens=data.get("usage", {}).get("completion_tokens", 0)
            )
        except httpx.TimeoutException:
            raise ProviderTimeoutError("OpenRouter timeout during completion.")
        except httpx.HTTPStatusError as e:
            raise ProviderError(f"OpenRouter API error: {e.response.status_code}")

    async def stream(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        payload = request.model_dump()
        payload["stream"] = True
        
        try:
            async with self.client.stream("POST", "/chat/completions", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        chunk = json.loads(line[6:])
                        delta = chunk["choices"][0].get("delta", {})
                        if "content" in delta:
                            yield delta["content"]
        except httpx.TimeoutException:
            raise ProviderTimeoutError("OpenRouter timeout during stream.")

    async def close(self):
        await self.client.aclose()