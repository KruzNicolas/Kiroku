# FastAPI Modular Monolith Refactor Plan

## Purpose

This document describes what will change in the project and how the migration will be executed safely.

---

## 1) Migration Strategies

### A. Incremental Refactor (Recommended)

#### What it means
Move from legacy architecture to FastAPI in controlled phases while keeping behavior operational.

#### How it would be executed
1. **Create target architecture skeleton** (`app/`, `shared/`, `modules/`) without deleting current code.
2. **Extract shared infrastructure first** (config, Notion client, global Notion save layer).
3. **Migrate one module at a time** (start with `videos`) with compatibility adapters.
4. **Expose FastAPI endpoints** for migrated flows while keeping temporary fallback compatibility.
5. **Validate parity** (same outputs, same Notion writes, same idempotency guarantees).
6. **Gradually deprecate old paths** once new module behavior is proven stable.

#### Pros
- Lower risk of production breakage.
- Easier rollback per phase.
- Better observability of regressions.

#### Cons
- Temporary duplication of code.
- Slightly slower delivery timeline.

---

### B. Big-Bang Migration

#### What it means
Replace all current legacy code with a complete FastAPI architecture in one large change.

#### How it would be executed
1. Freeze feature work.
2. Rewrite architecture and entrypoints fully in a dedicated branch.
3. Perform one-shot cutover to FastAPI.
4. Fix all regressions post-cutover.

#### Pros
- Single migration event.
- No temporary dual structure.

#### Cons
- Highest risk strategy.
- Hard rollback.
- Debugging becomes slower because many variables change at once.

---

## 2) Selected Approach

**Selected approach: Incremental Refactor.**

Reason: the project has external integrations (Notion/Ollama/yt-dlp) and idempotent persistence behavior that should not be destabilized by a full one-shot rewrite.

---

## 3) Planned Target Architecture

```text
app/
  main.py
  shared/
    config/
      settings.py
    notion/
      client.py
      contracts.py
      save_layer.py
    observability/
      logging.py
    errors/
      handlers.py
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

### Core architectural rules
- Modular monolith boundaries must be enforced.
- No module can import another module's application services.
- Shared concerns remain in `app/shared/*`.
- Notion writes are centralized in `app/shared/notion/save_layer.py`.
- Each module owns its own Notion database id.
- No Docker/container/cloud infrastructure work is allowed during this migration stage.

---

## 4) Detailed Change Plan (Phased)

### Phase 0 — Baseline and Safety
- Add architecture governance docs.
- Define migration guardrails and non-goals.
- Keep legacy flow untouched.

### Phase 1 — FastAPI Skeleton
- Create `app/main.py` with application factory and health endpoint.
- Add shared settings/loading strategy.
- Add dependency wiring scaffolding.

### Phase 2 — Shared Notion Persistence Layer
- Create `app/shared/notion/client.py`.
- Create `app/shared/notion/contracts.py` for generic save contract.
- Create `app/shared/notion/save_layer.py` as the only write gateway.
- Implement upsert-by-URL in the shared layer.

### Phase 3 — Videos Module Migration
- Create `app/modules/videos/*` structure.
- Move extraction and inference logic behind videos infrastructure adapters.
- Keep module-specific `database_id` in `module_config.py`.
- Route writes through shared save layer only.

### Phase 4 — API Surface and Compatibility
- Add videos endpoint(s) in FastAPI.
- Ensure request/response schemas match expected behavior.
- Keep temporary fallback until functional parity is verified.

### Phase 5 — Hardening and Cleanup
- Add structured logging and error mapping.
- Remove deprecated legacy internals after parity confirmation.
- Document deployment path for VPS.
- Do not introduce Docker/container/cloud infrastructure changes in this phase.

---

## 5) Risks and Mitigations

### Risk: blocking I/O in API context
- **Cause**: `yt-dlp`, `notion-client`, and inference client are synchronous.
- **Mitigation**: execute blocking calls via threadpool adapters and control concurrency.

### Risk: external API rate limits (Notion/Ollama)
- **Mitigation**: centralize retries, backoff, and error normalization in shared integration layers.

### Risk: duplicate writes under retries
- **Mitigation**: enforce URL-based upsert strategy and idempotency checks in shared save layer.

### Risk: architecture drift into cross-module coupling
- **Mitigation**: strict import boundaries + code review checklist.

---

## 6) Done Criteria

Migration is considered successful when:
1. FastAPI app serves videos endpoints.
2. Videos module writes to Notion through shared save layer only.
3. Module-specific Notion DB IDs are isolated in module config.
4. Existing functional behavior remains compatible.
5. Internal structure follows modular monolith boundaries.
