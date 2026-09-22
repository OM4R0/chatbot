from pydantic import BaseModel
from typing import List, Literal

class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str

class ChatRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: float = 0.7
    stream: bool = False

class ChatResponse(BaseModel):
    id: str
    model: str
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0

class ProviderModel(BaseModel):
    id: str
    owned_by: str