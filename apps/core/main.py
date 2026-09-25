import httpx
import hashlib
import json
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from apps.core.config import settings

http_client = None


def build_external_conversation_id(
    body: dict, headers, client_host: str | None = None
) -> str | None:
    """Preserve a conversation when an OpenAI-compatible client omits its ID."""
    for header in ("x-open-webui-chat-id", "x-conversation-id", "x-chat-id"):
        value = headers.get(header)
        if value:
            return value

    # Open WebUI sends user identity headers but not necessarily a chat ID to
    # external OpenAI-compatible connections. The first user message is stable
    # for the life of a chat, so a hash gives the database a safe stable key
    # without storing that text as an identifier.
    identity = headers.get("x-open-webui-user-id") or body.get("user") or client_host
    first_user_message = next(
        (
            message.get("content")
            for message in body.get("messages", [])
            if isinstance(message, dict) and message.get("role") == "user"
        ),
        None,
    )
    if not identity or first_user_message is None:
        return None

    source = json.dumps(
        {"identity": str(identity), "first_user_message": first_user_message},
        sort_keys=True,
        ensure_ascii=False,
    )
    return "derived:" + hashlib.sha256(source.encode("utf-8")).hexdigest()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    http_client = httpx.AsyncClient(timeout=httpx.Timeout(settings.provider_timeout))
    yield
    if http_client:
        await http_client.aclose()

app = FastAPI(lifespan=lifespan, title="Core API")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "core"}

@app.get("/v1/models")
async def list_models():
    try:
        response = await http_client.get(f"{settings.orchestrator_url}/v1/models")
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Orchestrator is unavailable")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/models/{model_id}")
async def get_model(model_id: str):
    try:
        response = await http_client.get(f"{settings.orchestrator_url}/v1/models/{model_id}")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Model not found")
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Orchestrator is unavailable")

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    headers_to_forward = {}
    conversation_id = build_external_conversation_id(
        body, request.headers, request.client.host if request.client else None
    )
    if conversation_id:
        headers_to_forward["x-external-conversation-id"] = conversation_id

    user_id = request.headers.get("x-open-webui-user-id")
    if user_id:
        headers_to_forward["x-external-user-id"] = user_id

    try:
        is_stream = bool(body.get("stream", False))
        target_url = f"{settings.orchestrator_url}/v1/orchestrate"

        # The orchestrator uses a complete response so it can retry OpenRouter
        # with Ollama before exposing any partial output. Convert that response
        # to standards-compliant SSE below when a client requested streaming.
        body["stream"] = False
        response = await http_client.post(target_url, json=body, headers=headers_to_forward)

        if response.status_code != 200:
            error_detail = "Orchestrator error"
            try:
                error_data = response.json()
                if isinstance(error_data, dict):
                    if "error" in error_data:
                        error_detail = error_data["error"]
                    elif "detail" in error_data:
                        error_detail = error_data["detail"]
            except Exception:
                pass
            return JSONResponse(
                status_code=response.status_code,
                content={"error": {"message": error_detail, "type": "server_error"}}
            )

        data = response.json()
        response_id = f"chatcmpl-{data.get('id', '')}"
        created = int(time.time())
        model = data.get("model", body.get("model", ""))
        provider = data.get("provider", "unknown")
        response_headers = {"X-AI-Provider": provider}
        if data.get("fallback_from_model"):
            response_headers["X-AI-Fallback-From"] = data["fallback_from_model"]

        if is_stream:
            async def generate():
                first_chunk = {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {"role": "assistant", "content": data.get("content", "")},
                        "finish_reason": None,
                    }],
                }
                final_chunk = {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                yield f"data: {json.dumps(first_chunk)}\n\n"
                yield f"data: {json.dumps(final_chunk)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                generate(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                    **response_headers,
                },
            )

        openai_response = {
            "id": response_id,
            "object": "chat.completion",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": data.get("content", "")},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": data.get("prompt_tokens", 0),
                "completion_tokens": data.get("completion_tokens", 0),
                "total_tokens": data.get("prompt_tokens", 0) + data.get("completion_tokens", 0),
            },
        }
        return JSONResponse(content=openai_response, headers=response_headers)

    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Orchestrator is unavailable")
    except httpx.ReadTimeout:
        raise HTTPException(status_code=504, detail="Request to Orchestrator timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
