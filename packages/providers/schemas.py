from pydantic import BaseModel
from typing import List, Literal

class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str

class ChatRequest(BaseModel):
    # New chats use OpenRouter's free router until the client selects a model.
    model: str = "openrouter/free"
    messages: List[Message]
    temperature: float = 0.7
    stream: bool = False

class ChatResponse(BaseModel):
    id: str
    model: str
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    provider: str | None = None
    fallback_from_model: str | None = None

class ProviderModel(BaseModel):
    id: str
    owned_by: str
