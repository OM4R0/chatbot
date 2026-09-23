import json
import uuid
from typing import List, AsyncGenerator

import httpx

from .base import AIProvider
from .schemas import ChatRequest, ChatResponse, ProviderModel
from .exceptions import ProviderAPIError, ProviderConnectionError, ProviderTimeoutError

class OllamaProvider(AIProvider):
    def __init__(self, base_url: str = "http://localhost:11434", timeout: float = 120.0):
        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout),
        )

    @staticmethod
    def _api_error(response: httpx.Response) -> ProviderAPIError:
        try:
            detail = response.json().get("error")
        except (ValueError, AttributeError):
            detail = None
        detail = detail or response.text or response.reason_phrase
        return ProviderAPIError(
            f"Ollama API error ({response.status_code}): {detail}", response.status_code
        )

    async def list_models(self) -> List[ProviderModel]:
        try:
            response = await self.client.get("/api/tags")
            if response.is_error:
                raise self._api_error(response)
            data = response.json()
            return [
                ProviderModel(id=m["name"], owned_by="ollama") 
                for m in data.get("models", [])
            ]
        except httpx.TimeoutException:
            raise ProviderTimeoutError("Ollama timeout fetching models.")
        except httpx.RequestError as e:
            raise ProviderConnectionError(f"Ollama connection error: {e}")

    async def complete(self, request: ChatRequest) -> ChatResponse:
        payload = {
            "model": request.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": False,
            "options": {"temperature": request.temperature}
        }
        
        try:
            response = await self.client.post("/api/chat", json=payload)
            if response.is_error:
                raise self._api_error(response)
            data = response.json()
            
            return ChatResponse(
                id=str(uuid.uuid4()),
                model=data["model"],
                content=data["message"]["content"],
                prompt_tokens=data.get("prompt_eval_count", 0),
                completion_tokens=data.get("eval_count", 0)
            )
        except httpx.TimeoutException:
            raise ProviderTimeoutError("Ollama timeout during completion.")
        except httpx.RequestError as e:
            raise ProviderConnectionError(f"Ollama connection error: {e}")

    async def stream(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        payload = {
            "model": request.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": True,
            "options": {"temperature": request.temperature}
        }
        
        try:
            async with self.client.stream("POST", "/api/chat", json=payload) as response:
                if response.is_error:
                    await response.aread()
                    raise self._api_error(response)
                async for line in response.aiter_lines():
                    if line.strip():
                        chunk = json.loads(line)
                        if "message" in chunk and "content" in chunk["message"]:
                            yield chunk["message"]["content"]
        except httpx.TimeoutException:
            raise ProviderTimeoutError("Ollama timeout during stream.")
        except httpx.RequestError as e:
            raise ProviderConnectionError(f"Ollama connection error: {e}")

    async def close(self):
        await self.client.aclose()
