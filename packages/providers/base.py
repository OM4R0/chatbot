from abc import ABC, abstractmethod
from typing import List, AsyncGenerator
from .schemas import ChatRequest, ChatResponse, ProviderModel

class AIProvider(ABC):
    @abstractmethod
    async def list_models(self) -> List[ProviderModel]:
        pass

    @abstractmethod
    async def complete(self, request: ChatRequest) -> ChatResponse:
        pass

    @abstractmethod
    async def stream(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        pass

    @abstractmethod
    async def close(self):
        pass