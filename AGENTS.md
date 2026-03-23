# Project AI Collaboration Rules (OpenCode)

This file defines project-specific guidance for AI assistants working in this repository.

## Project Context

- Project name: `Kiroku`
- Current state: FastAPI modular monolith API
- Target state: FastAPI modular monolith for VPS deployment
- Primary external integrations:
  - Notion API (database persistence)
  - Ollama API (inference)
  - YouTube metadata extraction (`yt-dlp`)

## Tech Stack

- **Language**: Python 3.11+
- **Backend Framework (target)**: FastAPI
- **Validation/Models**: Pydantic
- **HTTP/API serving**: Uvicorn + FastAPI
- **Retries**: Tenacity
- **Notion SDK**: `notion-client`
- **Metadata extraction**: `yt-dlp`
- **Inference client**: `ollama`
- **Environment management**: `.env` + `python-dotenv`

## Architecture Rules

1. Use a **modular monolith** architecture under `app/modules/*`.
2. Each module is isolated:
   - No direct service-to-service calls between modules.
   - No importing another module's application services.
3. Shared concerns belong in `app/shared/*` only.
4. Notion persistence is centralized in a global shared layer:
   - `app/shared/notion/save_layer.py` is the single write gateway.
   - Each module provides its own `database_id` (module-owned configuration).
5. Keep clear boundaries:
   - `domain` (business rules)
   - `application` (use cases)
   - `infrastructure` (adapters/SDK wiring)
   - `api` (FastAPI router/contracts)

## FastAPI Folder Convention

Recommended target structure:

```text
app/
  main.py
  shared/
    config/
    notion/
      client.py
      save_layer.py
      contracts.py
    observability/
    errors/
  modules/
    videos/
      api/router.py
      application/service.py
      domain/models.py
      infrastructure/
        extractors.py
        inferencer.py
      module_config.py
```

## Coding Standards

- Prefer explicit dependency injection over hidden globals.
- Keep routers thin; business logic must live in application/domain layers.
- Use typed DTOs and response models for all endpoints.
- Handle retries/rate limits in shared integration layers.
- Enforce idempotent Notion writes (upsert strategy).
- Add structured logging for request traceability.

## Migration Constraints

- Do not break existing behavior during migration unless explicitly approved.
- Migrate incrementally in phases (strangler approach preferred).
- Preserve current Notion schema compatibility unless a migration is planned.
- Avoid introducing cross-module coupling during refactor.
- Do not add Docker, containerization, or cloud infrastructure changes until explicitly requested.

## Non-Goals (for this phase)

- No forced split into distributed microservices.
- No premature Kubernetes/distributed infra complexity.
- No direct module-to-module orchestration.
