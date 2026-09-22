from typing import TypedDict, Optional
import uuid
from packages.providers.schemas import ChatRequest, ChatResponse

class OrchestratorState(TypedDict):
    """Task 22: Define orchestration state for LangGraph nodes."""
    
    # Input data
    request: ChatRequest
    request_id: str
    external_conversation_id: Optional[str]
    
    # Database Identifiers
    conversation_id: Optional[uuid.UUID]
    run_id: Optional[uuid.UUID]
    
    # Execution details
    selected_provider: Optional[str]
    provider_response: Optional[ChatResponse]
    
    # Guardrails and workflow control
    is_safe: bool
    error: Optional[str]