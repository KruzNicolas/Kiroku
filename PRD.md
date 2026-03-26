# PRD: Kiroku API + Bot Gateway + Deployment

**Version**: 1.0.0  
**Date**: 2026-03-25  
**Status**: Active

---

## 1) Overview

Kiroku is a FastAPI modular monolith focused on personal ingestion workflows from Discord/Telegram bots.

Current modules:

- `videos`: ingest YouTube links, classify with AI, persist to Notion.
- `receipts`: ingest receipt images/manual purchases, extract/validate, send to Google Sheets.
- `study_assets` (Japanese): ingest image inbox items for later manual card creation.

Bots act as transport adapters only; business logic remains in Kiroku API.

---

## 2) Product Goals

1. Accept bot-originated content through hardened API endpoints.
2. Prevent duplicate processing with idempotency.
3. Enforce source-aware rate limits.
4. Keep clear auditability through structured source headers/logs.
5. Preserve modular boundaries while integrating Notion, Ollama, yt-dlp, and Sheets.

---

## 3) API Modules and Endpoint Contracts

### 3.1 Videos

Endpoints:

- `POST /api/v1/videos`
- `POST /api/v1/videos/batch`

Flow:

1. Extract metadata via `yt-dlp` (title/channel/description/tags/game category).
2. Classify via AI inferencer.
3. Persist to Notion with:
   - `Title`, `Channel`, `URL`, `Category`, `Priority`, `Confidence`, `Added at`
4. Write AI rationale in Notion page body.

Notes:

- Upsert key is URL (`same URL => update existing row`).
- `Added at` is generated from configured business timezone.

### 3.2 Receipts

Endpoints:

- `POST /api/v1/receipts` (multipart image OCR flow)
- `POST /api/v1/receipts/manual` (JSON manual flow)

OCR flow input:

- `receipt_image` (required; jpeg/png)
- `store_hint` (optional)
- `batch_category` (optional)
- `request_id` (optional)

Manual flow input:

- `date`, `category`, `store`, `items[{product, quantity, price}]`
- `request_id` optional

Notes:

- Quantity preserves decimal values for weighted products.
- Prices are normalized for COP whole-unit handling.
- `batch_category` overrides per-item inferred category when provided.

### 3.3 Japanese Study Assets

Endpoint:

- `POST /api/v1/study-assets/japanese`

Input (`multipart/form-data`):

- `image` required (jpeg/png)
- `note` optional

Behavior:

- Uploads image through Notion File Upload API.
- Creates new Notion page with:
  - `Title` (generated id-like title)
  - `Image` (files)
  - `Status` (`Pending`)
  - `Note` (optional)
  - `Added at` (business date)

---

## 4) Security and Gateway Hardening

All `/api/v1/*` endpoints are bot-gated.

Required:

- `Authorization: Bearer <INTERNAL_API_TOKEN>`

Recommended and used by bots:

- `X-Source`
- `X-Source-Message-Id`
- `X-Source-User-Id`
- `Idempotency-Key`

Hardening behaviors:

1. Internal token auth
2. Idempotent replay by source+key with TTL
3. Per-endpoint/source rate limits
4. Structured audit logging

---

## 5) Bot Adapter PRD (Discord)

### 5.1 Scope

Discord bot routes channel traffic to Kiroku endpoints. It is a transport adapter only.

### 5.2 Channel-gated routing (no slash command requirement)

- `videos` -> one/multiple YouTube URLs -> single/batch videos endpoint
- `receipts` -> image + optional store text -> receipts OCR endpoint
- `receipts-manual` -> structured text payload -> receipts manual endpoint
- `study-japanese` -> image + optional note -> japanese endpoint

### 5.3 Security validation order

1. Ignore bot/system messages
2. Validate allowlisted `guild_id`
3. Validate allowlisted `channel_id`
4. Validate allowlisted `user_id` (if configured)
5. Validate payload type for channel

### 5.4 Idempotency key format

- `discord:<guild_id>:<channel_id>:<message_id>`

### 5.5 Retry and error matrix

- Retry only: `429`, `502`, `503`, timeouts
- No retry: `400`, `401`, `403`, `404`, `422`
- Max 3 attempts, exponential backoff with jitter

### 5.6 UX

- `⏳` processing
- `✅` success
- `❌` failure
- `🔁` retry trigger

Batch partial failure behavior:

1. Post failed URLs summary
2. Authorized user reacts with `🔁`
3. Retry only failed URLs

---

## 6) Bot Adapter PRD (Telegram)

### 6.1 Scope

Telegram bot receives webhook updates and routes to Kiroku endpoints.

### 6.2 Security

- Validate `X-Telegram-Bot-Api-Secret-Token`
- Allowlist `chat_id` / optional `user_id`
- Forward standard source/idempotency headers to API

### 6.3 Idempotency key format

- `telegram:<chat_id>:<update_id>`

### 6.4 Retry policy

Same policy as Discord:

- Retry only `429/502/503/timeouts`
- Max 3 attempts with backoff+jitter

---

## 7) Architecture and Repository Split

Recommended split:

1. `kiroku-api` (this repository): domain + modules + integrations
2. `kiroku-bots`: Discord + Telegram transport adapters
3. `kiroku-deploy`: Docker Compose, proxy, env/secrets wiring, operations

Runtime topology (VPS):

- `kiroku-api`
- `discord-bot`
- `telegram-bot`
- `redis` (for persistent idempotency/rate-limit state)
- reverse proxy (`caddy`/`nginx`)

---

## 8) CI/CD and Deployment Plan

### API and bots repos

- PR: tests (+ optional lint)
- Merge main: build Docker image and push to GHCR

### Deploy repo

Manual/approved deploy cycle:

1. update image tags
2. `docker compose pull`
3. `docker compose up -d`
4. smoke checks

Rollback: revert tags and redeploy.

---

## 9) Current Gaps and Next Steps

1. Move idempotency/rate-limit from in-memory to Redis for production durability.
2. Complete Discord bot MVP first, then Telegram bot.
3. Add deploy runbook (deploy, smoke test, rollback).
4. Add alerting baseline for repeated 5xx/upstream failures.

---

## 10) Definition of Done (current stage)

1. Bot-authenticated API endpoints operational.
2. Idempotency and rate-limit behavior validated end-to-end.
3. Discord adapter routes flows correctly with clear feedback.
4. All core flows persisted correctly:
   - videos -> Notion
   - japanese assets -> Notion files
   - receipts -> Google Sheets
5. Services deploy reproducibly on VPS through compose-driven workflow.
