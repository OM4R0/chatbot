# Chatbot Platform

## Free OpenRouter with automatic local fallback

The client should connect to `http://localhost:8000/v1` (or Open WebUI at
`http://localhost:3000`). New chats use `openrouter/free` by default, while
the application exposes the complete OpenRouter model catalog. Selecting a
paid model sends that exact model ID to OpenRouter, so it becomes available as
soon as the account has credits.

If OpenRouter is out of credits, rate-limited, unavailable, times out, or
returns another API error, the same request is automatically retried against
the Ollama model in `DEFAULT_FALLBACK_MODEL` (default: `qwen2.5:3b`). Docker
Compose pulls that model before starting the orchestrator, so the fallback is
ready rather than failing on its first use.

1. Copy `.env.example` to `.env` and set `OPENROUTER_API_KEY`.
2. Start everything with `docker compose up --build`.
3. Choose `openrouter/free`, a free `:free` model, or any paid model once the
   account has credits. The `/v1/models` endpoint also includes local Ollama
   models.

For a local, non-Docker backend, set `OLLAMA_BASE_URL=http://localhost:11434`
in `.env` and make sure the fallback model is pulled with
`ollama pull qwen2.5:3b`.

## Clean Code Rules

- Keep functions small and focused.
- Depend on interfaces instead of concrete provider clients.
- Do not place database, provider, or orchestration logic in route handlers.
- Use dependency injection for replaceable components.
- Avoid duplicated implementations and unused abstractions.
