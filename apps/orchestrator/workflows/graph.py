from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langchain_core.runnables.config import RunnableConfig

from .state import OrchestratorState
from .guardrails import GuardrailService
from apps.orchestrator.services.tracking import TrackingService
from apps.orchestrator.services.conversation import ConversationService
from apps.orchestrator.services.models import model_service
from packages.persistence.models.run import RunStatus

# --- Define Nodes ---

async def input_node(state: OrchestratorState, config: RunnableConfig) -> Dict[str, Any]:
    """Node 1: Input Validation."""
    session = config["configurable"]["session"]
    is_safe, error_msg = GuardrailService.validate_input(state["request"])
    
    if not is_safe:
        # Log to AuditEvents
        await TrackingService.log_audit(
            session=session,
            request_id=state["request_id"],
            event_type="input_guardrail",
            action="rejected",
            payload={"reason": error_msg}
        )
        return {"is_safe": False, "error": error_msg}
        
    return {"is_safe": True}

async def prepare_node(state: OrchestratorState, config: RunnableConfig) -> Dict[str, Any]:
    """Node 2: Setup DB Conversation & Create Run."""
    session = config["configurable"]["session"]
    request = state["request"]
    
    conversation = await ConversationService.get_or_create_conversation(
        session, state["external_conversation_id"]
    )
    
    provider = await model_service.resolve_provider(request.model)
    provider_name = provider.__class__.__name__.replace("Provider", "").lower()
    
    run = await TrackingService.create_run(
        session=session,
        conversation_id=conversation.id,
        provider=provider_name,
        model_name=request.model
    )
    
    return {
        "conversation_id": conversation.id,
        "run_id": run.id,
        "selected_provider": provider_name
    }

async def execute_node(state: OrchestratorState, config: RunnableConfig) -> Dict[str, Any]:
    """Node 3: Call AI Provider."""
    provider = await model_service.resolve_provider(state["request"].model)
    
    try:
        response = await provider.complete(state["request"])
        return {"provider_response": response}
    except Exception as e:
        return {"is_safe": False, "error": str(e)}

async def output_node(state: OrchestratorState, config: RunnableConfig) -> Dict[str, Any]:
    """Node 4: Validate Output & Finalize DB."""
    session = config["configurable"]["session"]
    response = state["provider_response"]
    run_id = state["run_id"]
    
    if not response:
        await TrackingService.update_run(session, run_id, status=RunStatus.FAILED, error_message=state["error"])
        return {}

    is_safe, error_msg = GuardrailService.validate_output(response)
    
    if not is_safe:
        await TrackingService.log_audit(
            session, state["request_id"], "output_guardrail", "rejected", run_id, {"reason": error_msg}
        )
        await TrackingService.update_run(session, run_id, status=RunStatus.FAILED, error_message="Output validation failed")
        return {"is_safe": False, "error": error_msg}

    # Save to DB transactionally
    await ConversationService.add_messages_to_conversation(
        session, state["conversation_id"], state["request"].messages
    )
    
    await TrackingService.update_run(
        session, run_id, RunStatus.COMPLETED, 
        response.prompt_tokens, response.completion_tokens
    )
    
    return {"is_safe": True}

# --- Define Routing Logic ---

def route_after_input(state: OrchestratorState) -> str:
    return "prepare" if state["is_safe"] else END

def route_after_execute(state: OrchestratorState) -> str:
    return "output" if state["is_safe"] else END

# --- Build the Graph ---

def build_workflow() -> StateGraph:
    """Compile the LangGraph workflow."""
    workflow = StateGraph(OrchestratorState)
    
    workflow.add_node("input", input_node)
    workflow.add_node("prepare", prepare_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("output", output_node)
    
    workflow.set_entry_point("input")
    workflow.add_conditional_edges("input", route_after_input)
    workflow.add_edge("prepare", "execute")
    workflow.add_conditional_edges("execute", route_after_execute)
    workflow.add_edge("output", END)
    
    return workflow.compile()

orchestrator_graph = build_workflow()