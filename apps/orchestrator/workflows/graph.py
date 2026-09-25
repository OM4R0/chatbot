from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langchain_core.runnables.config import RunnableConfig

from .state import OrchestratorState
from .guardrails import GuardrailService
from apps.orchestrator.services.tracking import TrackingService
from apps.orchestrator.services.conversation import ConversationService
from apps.orchestrator.services.models import model_service
from packages.persistence.models.run import RunStatus
from packages.providers.schemas import Message as ProviderMessage

# --- Define Nodes ---

async def input_node(state: OrchestratorState, config: RunnableConfig) -> Dict[str, Any]:
    """Node 1: Input Validation."""
    session = config["configurable"]["session"]
    is_safe, error_msg = GuardrailService.validate_input(state["request"])
    
    if not is_safe:
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
    stored_messages = await ConversationService.get_messages(session, conversation.id)
    messages_to_persist = ConversationService.new_messages_since(
        stored_messages, request.messages
    )
    request_with_history = request.model_copy(
        update={"messages": [*stored_messages, *messages_to_persist]}
    )
    
    provider = await model_service.resolve_provider(request.model)
    provider_name = model_service.provider_name(provider)
    
    run = await TrackingService.create_run(
        session=session,
        conversation_id=conversation.id,
        provider=provider_name,
        model_name=request.model
    )
    
    return {
        "conversation_id": conversation.id,
        "run_id": run.id,
        "selected_provider": provider_name,
        "request": request_with_history,
        "messages_to_persist": messages_to_persist,
    }

async def execute_node(state: OrchestratorState, config: RunnableConfig) -> Dict[str, Any]:
    """Call OpenRouter, then automatically fail over to Ollama on any error."""
    request = state["request"]
    session = config["configurable"]["session"]
    run_id = state["run_id"]
    primary_error: Exception | None = None

    try:
        provider = await model_service.resolve_provider(request.model)
        primary_name = model_service.provider_name(provider)
        response = await provider.complete(model_service.request_for(provider, request))
        return {
            "provider_response": response,
            "selected_provider": primary_name,
            "selected_model": response.model,
        }
    except Exception as exc:
        primary_error = exc

    # A quota/credit error (and all other OpenRouter failures) uses the same
    # local fallback. Never pass the remote OpenRouter model id to Ollama.
    ollama_provider = model_service.providers.get("ollama")
    if ollama_provider and model_service.provider_name(ollama_provider) != state.get("selected_provider"):
        try:
            fallback_request = model_service.request_for(ollama_provider, request)
            fallback_request.model = model_service.fallback_model
            response = await ollama_provider.complete(fallback_request)
            response = response.model_copy(
                update={
                    "content": (
                        "⚠️ OpenRouter could not serve the selected model. "
                        f"This response was generated locally by Ollama ({response.model}).\n\n"
                        f"{response.content}"
                    ),
                    "provider": "ollama",
                    "fallback_from_model": request.model,
                }
            )
            await TrackingService.log_audit(
                session=session,
                request_id=state["request_id"],
                event_type="provider_fallback",
                action="ollama_selected",
                run_id=run_id,
                payload={
                    "from_provider": state.get("selected_provider", "openrouter"),
                    "from_model": request.model,
                    "to_model": response.model,
                    "reason": str(primary_error),
                },
            )
            return {
                "provider_response": response,
                "selected_provider": "ollama",
                "selected_model": response.model,
                "fallback_from_model": request.model,
            }
        except Exception as fallback_error:
            error_msg = f"All providers failed. Ollama: {fallback_error}. OpenRouter: {primary_error}"
    else:
        error_msg = str(primary_error) if primary_error else "No provider available."

    await TrackingService.update_run(
        session, run_id, RunStatus.FAILED, error_message=error_msg
    )
    return {"is_safe": False, "error": error_msg}

async def output_node(state: OrchestratorState, config: RunnableConfig) -> Dict[str, Any]:
    """Node 4: Validate Output & Finalize DB."""
    session = config["configurable"]["session"]
    response = state.get("provider_response")
    run_id = state.get("run_id")
    
    if not response:
        error_msg = state.get("error", "Unknown execution failure")
        if run_id:
            await TrackingService.update_run(
                session, run_id, status=RunStatus.FAILED, error_message=error_msg
            )
        return {"is_safe": False, "error": error_msg}

    is_safe, error_msg = GuardrailService.validate_output(response)
    
    if not is_safe:
        await TrackingService.log_audit(
            session, state["request_id"], "output_guardrail", "rejected", run_id, {"reason": error_msg}
        )
        await TrackingService.update_run(session, run_id, status=RunStatus.FAILED, error_message="Output validation failed")
        return {"is_safe": False, "error": error_msg}

    # Save both sides of the exchange as part of the same transaction as the
    # run update, so a fallback response is tracked consistently.
    await ConversationService.add_messages_to_conversation(
        session,
        state["conversation_id"],
        [
            *state.get("messages_to_persist", state["request"].messages),
            ProviderMessage(role="assistant", content=response.content),
        ],
    )
    
    await TrackingService.update_run(
        session, run_id, RunStatus.COMPLETED, 
        response.prompt_tokens,
        response.completion_tokens,
        provider=state.get("selected_provider"),
        model_name=state.get("selected_model", response.model),
    )
    
    return {"is_safe": True}

# --- Routing Logic ---

def route_after_input(state: OrchestratorState) -> str:
    return "prepare" if state.get("is_safe", True) else END

def route_after_execute(state: OrchestratorState) -> str:
    return "output" if state.get("is_safe", True) else END

# --- Build Workflow ---

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
