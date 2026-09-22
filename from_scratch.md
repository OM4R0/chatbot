# ChatbotAA - Build From Scratch

## Project goal

Build an AI chat platform as a monorepo containing two independent
microservices:

```text
Browser -> Open WebUI -> Core API -> Orchestrator API -> AI provider
                                      |
                                 PostgreSQL
```

- **Core API:** Public OpenAI-compatible gateway.
- **Orchestrator API:** Runs guardrails, model routing, chat workflows, and
  persistence.
- **Open WebUI:** Browser interface.

Each service must have one responsibility, its own starter module, health
check, configuration, tests, and Docker service.

## Phase 1 - Monorepo foundation

### Task 1: Create the repository structure

Create one repository containing both services and their shared packages.

```text
apps/
  core/
  orchestrator/
packages/
  common/
  providers/
  persistence/
tests/
alembic/
```

Keep service-specific code inside its service. Put code in `packages/` only
when both services genuinely need it.

**Deliverable:** Both service directories and their Python packages exist.

### Task 2: Configure the Python project

- Use Python 3.12.
- Add FastAPI, Uvicorn, Pydantic, HTTPX, SQLAlchemy, Alembic, LangGraph, and
  pytest.
- Lock dependency versions.

**Deliverable:** Dependencies install with one command from the repository root.

### Task 3: Add environment configuration

- Create typed settings using Pydantic.
- Read ports, database URLs, provider URLs, timeouts, and secrets from `.env`.
- Provide `.env.example` without real secrets.
- Fail clearly when a required value is missing.

**Deliverable:** Both services can load and validate their configuration.

### Task 4: Establish clean-code rules

- Keep functions small and focused.
- Depend on interfaces instead of concrete provider clients. (coding clients)
- Do not place database, provider, or orchestration logic in route handlers.
- Use dependency injection for replaceable components.
- Avoid duplicated implementations and unused abstractions.

**Deliverable:** Add these rules to the project README and enforce linting.

## Phase 2 - Local infrastructure

### Task 5: Add PostgreSQL

- Run PostgreSQL with Docker Compose.
- Add a persistent named volume and health check.
- Make PostgreSQL accessible only to the service that owns persistence.

**Deliverable:** PostgreSQL starts healthy and keeps data after restart.

### Task 6: Add Redis

- Run Redis with Docker Compose.
- Add persistence and a health check.
- Use it only for temporary state, caching, or workflow coordination.

**Deliverable:** Redis starts healthy and responds to a ping.

### Task 7: Create separate service starters

- Create `apps/core/main.py` for Core.
- Create `apps/orchestrator/main.py` for Orchestrator.
- Run Core on port `8000` and Orchestrator on port `8001`.
- Add `GET /health` to both services.

**Deliverable:** Both services run at the same time as separate processes.

## Phase 3 - Persistence

### Task 8: Create the async database layer

- Create the SQLAlchemy async engine and session factory.
- Open sessions through dependency injection.
- Close connections cleanly during shutdown.

**Deliverable:** Orchestrator can connect to PostgreSQL asynchronously.

### Task 9: Model conversations and messages

- Store conversations with internal and optional external identifiers.
- Store ordered user and assistant messages.
- Record creation and update timestamps.

**Deliverable:** A conversation and its messages can be created and retrieved.

### Task 10: Model orchestration runs

- Store one run for every chat request.
- Track pending, completed, failed, and cancelled states.
- Store provider, model, token usage, and error information.

**Deliverable:** Every request leaves a traceable run record.

### Task 11: Model audit events

- Record important policy and workflow decisions.
- Include request and correlation identifiers.
- Never store provider secrets or sensitive headers.

**Deliverable:** Decisions can be traced without exposing secrets.

### Task 12: Add migrations

- Create explicit Alembic migrations for all tables and constraints.
- Run `alembic upgrade head` before Orchestrator starts.
- Never generate migrations automatically during application startup.

**Deliverable:** An empty database can be upgraded to the latest schema.

## Phase 4 - AI provider clients

### Task 13: Define the provider client contract

Create one interface for all AI providers. It should support:

- Listing models.
- Retrieving one model.
- Normal chat completion.
- Streaming chat completion.
- Closing connections.

Provider-specific SDK types must not escape this layer.

**Deliverable:** A fake client can implement the interface for tests.

### Task 14: Build the OpenRouter client

- Use its OpenAI-compatible API.
- Read the API key and base URL from configuration.
- Support normal and streaming responses.
- Apply timeouts and convert SDK errors into application exceptions.

**Deliverable:** The client can list models and complete a test request.

### Task 15: Build the Ollama client

- Connect to a configurable Ollama URL.
- Support model listing and chat completion.
- Allow Ollama to be disabled without breaking the application.
- Use the same provider interface as OpenRouter.

**Deliverable:** The model layer can use Ollama without special route logic.

### Task 16: Create provider exceptions

Define clear exceptions for unavailable providers, timeouts, rate limits,
invalid models, and unexpected responses. Route handlers should translate them
into consistent HTTP errors.

**Deliverable:** Provider failures never expose raw SDK exceptions to clients.

## Phase 5 - Model and conversation services

### Task 17: Build the model catalog

- Collect models from all enabled providers.
- Return a normalized OpenAI-compatible model shape.
- Keep provider details internal.

**Deliverable:** `GET /v1/models` returns one combined model list.

### Task 18: Build model selection

- Resolve each requested model to its provider.
- Reject unknown models clearly.
- Support an explicitly configured fallback.

**Deliverable:** A model request always selects one known provider.

### Task 19: Build the conversation service

- Create new conversations and continue existing ones.
- Store messages and orchestration results transactionally.
- Reject conflicting or unknown conversation identifiers.

**Deliverable:** Chat history remains consistent after success or failure.

## Phase 6 - Guardrails and orchestration

### Task 20: Add input guardrails

- Validate request structure and message content.
- Apply configured policies before provider calls.
- Return a clear rejection without calling a provider when validation fails.

**Deliverable:** Unsafe or invalid input stops before model execution.

### Task 21: Add output guardrails

- Validate provider output before returning it.
- Apply the same rules to normal and streaming responses.
- Record rejected output as an audit event.

**Deliverable:** Unapproved model output is not returned as a valid answer.

### Task 22: Define orchestration state

Create a typed state containing the request, selected provider, conversation,
guardrail results, provider response, and failure information.

**Deliverable:** Every graph node reads and writes a documented state field.

### Task 23: Build the LangGraph workflow

Create focused nodes for:

1. Input validation.
2. Conversation preparation.
3. Model selection.
4. Provider execution.
5. Output validation.
6. Persistence.
7. Final response creation.

**Deliverable:** One workflow handles both success and controlled failure paths.

### Task 24: Support streaming safely

- Stream provider events without changing their order.
- Collect enough data to persist the final assistant response.
- Mark disconnected streams as cancelled and failed streams as failed.

**Deliverable:** Streaming remains responsive and produces a correct run record.

## Phase 7 - Microservice APIs

### Task 25: Build the Orchestrator API

Expose:

- `POST /v1/orchestrate`
- `GET /v1/models`
- `GET /v1/models/{model_id}`
- `GET /health`

Routes should validate HTTP input and delegate all work to services. No
authentication is required for this exercise.

**Deliverable:** Orchestrator works independently on port `8001`.

### Task 26: Build the Core API

Expose the public OpenAI-compatible endpoints:

- `POST /v1/chat/completions`
- `GET /v1/models`
- `GET /v1/models/{model_id}`
- `GET /health`

Core must remain thin. It must not contain provider, guardrail, database, or
LangGraph logic.

**Deliverable:** Core works independently on port `8000`.

### Task 27: Connect Core to Orchestrator

- Map Core's `/v1/chat/completions` to Orchestrator's `/v1/orchestrate`.
- Forward request bodies, query parameters, request IDs, and relevant headers.
- Preserve JSON and server-sent event responses.
- Return `503` when Orchestrator is unavailable and `504` on timeout.
- Do not forward arbitrary paths or require internal authentication.

**Deliverable:** All public chat traffic passes through both microservices.

### Task 28: Protect service boundaries

- Give each service its own Docker service and startup command.
- Start Core only after Orchestrator becomes healthy.
- Keep Orchestrator responsible for persistence and AI workflows.
- Do not import Orchestrator runtime objects directly into Core.

**Deliverable:** Either service can be restarted without rebuilding the other.

## Phase 8 - Open WebUI

### Task 29: Add Open WebUI

- Run Open WebUI on port `3000`.
- Configure its OpenAI base URL as `http://core:8000/v1`.
- Disable API-key authentication for the Core connection.
- Read the administrator email, name, password, and secret key from `.env`.

**Deliverable:** A user can sign in and see the model catalog.

### Task 30: Connect conversation identifiers

- Forward the Open WebUI chat, user, and task identifiers through Core.
- Link an Open WebUI chat to one internal conversation.
- Prevent conflicting identifiers from being accepted.

**Deliverable:** Repeated messages continue the correct stored conversation.

## Phase 9 - Quality and delivery

### Task 31: Add structured logging

- Add request and correlation IDs to logs and responses.
- Log service startup, shutdown, request completion, and controlled failures.
- Never log passwords, API keys, or full sensitive prompts.

**Deliverable:** One request can be followed across Core and Orchestrator logs.

### Task 32: Create Docker images

- Give Core and Orchestrator independent image targets.
- Run each service as a non-root user.
- Keep images small and avoid copying `.env` or development files.

**Deliverable:** Each microservice can be built and deployed independently.

### Task 33: Complete Docker Compose

Connect Open WebUI, Core, Orchestrator, PostgreSQL, and Redis on one private
network. Add health checks, dependency conditions, environment variables, and
persistent volumes.

**Deliverable:** `docker compose up --build -d` starts the full platform.

### Task 34: Final verification

Demonstrate:

1. Both APIs report healthy on different ports.
2. Open WebUI lists models through Core.
3. A normal chat succeeds.
4. A streaming chat succeeds.
5. Conversation, run, message, and audit records are stored.

**Completion result:** A working monorepo with two cleanly separated,
independently runnable microservices and replaceable AI provider clients.
