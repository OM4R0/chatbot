import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from apps.orchestrator.config import settings
from packages.persistence.session import initialize_database, close_database, get_db_session
from packages.providers.schemas import ChatRequest, ChatResponse
from apps.orchestrator.workflows.graph import orchestrator_graph
from apps.orchestrator.services.models import model_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database(settings.database_url)
    yield
    await model_service.close()
    await close_database()

app = FastAPI(lifespan=lifespan, title="Orchestrator API", version="1.0")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "orchestrator"}

@app.get("/db-ping")
async def db_ping(session: AsyncSession = Depends(get_db_session)):
    return {"status": "db_connected"}

@app.get("/v1/models")
async def list_models():
    try:
        models = await model_service.get_all_models()

        # Format output to match OpenAI /v1/models response format
        formatted_models = []
        for m in models:
            formatted_models.append({
                "id": m.id,
                "object": "model",
                "created": 0,
                "owned_by": m.owned_by,
            })

        return {"object": "list", "data": formatted_models}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/models/{model_id}")
async def get_model(model_id: str):
    try:
        models = await model_service.get_all_models()
        for m in models:
            if m.id == model_id:
                return m.model_dump() if hasattr(m, 'model_dump') else m.dict()
        raise HTTPException(status_code=404, detail="Model not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/orchestrate")
async def orchestrate_chat(
    payload: ChatRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session)
):
    request_id = str(uuid.uuid4())
    ext_conv_id = request.headers.get("x-external-conversation-id", "")

    initial_state = {
        "request": payload,
        "request_id": request_id,
        "external_conversation_id": ext_conv_id,
        "is_safe": True,
    }

    config = {"configurable": {"session": session}}

    try:
        final_state = await orchestrator_graph.ainvoke(initial_state, config=config)

        if not final_state.get("is_safe", True):
            error_msg = final_state.get("error", "Request blocked by safety guardrails")
            status_code = 400 if "guardrail" in error_msg.lower() or "rejected" in error_msg.lower() else 503
            return JSONResponse(status_code=status_code, content={"error": error_msg})

        provider_response = final_state.get("provider_response")

        if not provider_response:
             raise HTTPException(status_code=500, detail="Failed to get response from AI provider")

        response = ChatResponse(
            id=str(final_state.get("run_id", uuid.uuid4())),
            model=provider_response.model,
            content=provider_response.content,
            prompt_tokens=provider_response.prompt_tokens,
            completion_tokens=provider_response.completion_tokens
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Orchestration failed: {str(e)}")
