# Kiroku API Endpoints Guide (Bot Usage)

This guide shows how to call each endpoint with the required headers and what responses to expect.

---

## Base URL

Local:

```bash
http://127.0.0.1:8000
```

---

## Required Headers for `/api/v1/*`

All bot-ingestion endpoints require:

- `Authorization: Bearer <INTERNAL_API_TOKEN>`
- `X-Source: discord-bot | telegram-bot`
- `Idempotency-Key: <unique-per-message>`

Recommended audit headers:

- `X-Source-Message-Id: <message/update id>`
- `X-Source-User-Id: <platform user id>`

Example reusable headers:

```bash
-H "Authorization: Bearer $INTERNAL_API_TOKEN" \
-H "X-Source: discord-bot" \
-H "X-Source-Message-Id: 123456789" \
-H "X-Source-User-Id: 987654321" \
-H "Idempotency-Key: discord:guild:channel:message"
```

---

## 1) Health

### Request

```bash
curl -X GET "http://127.0.0.1:8000/health"
```

### Response (200)

```json
{
  "status": "ok"
}
```

---

## 2) Create one video

### Endpoint

`POST /api/v1/videos`

### Request

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/videos" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $INTERNAL_API_TOKEN" \
  -H "X-Source: discord-bot" \
  -H "X-Source-Message-Id: msg-1001" \
  -H "X-Source-User-Id: user-77" \
  -H "Idempotency-Key: discord:g:c:msg-1001" \
  -d '{
    "url": "https://www.youtube.com/watch?v=abc123",
    "manual_priority": "later"
  }'
```

### Response (201)

```json
{
  "status": "ok",
  "page_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "url": "https://www.youtube.com/watch?v=abc123"
}
```

---

## 3) Create videos batch

### Endpoint

`POST /api/v1/videos/batch`

### Request

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/videos/batch" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $INTERNAL_API_TOKEN" \
  -H "X-Source: discord-bot" \
  -H "X-Source-Message-Id: msg-1002" \
  -H "X-Source-User-Id: user-77" \
  -H "Idempotency-Key: discord:g:c:msg-1002" \
  -d '{
    "items": [
      {"url": "https://www.youtube.com/watch?v=ok1"},
      {"url": "https://www.youtube.com/watch?v=ok2", "manual_priority": "low"}
    ],
    "max_workers": 2
  }'
```

### Response (200)

```json
{
  "status": "ok",
  "total": 2,
  "success_count": 2,
  "fail_count": 0,
  "failed_urls": [],
  "results": [
    {
      "success": true,
      "url": "https://www.youtube.com/watch?v=ok1",
      "page_id": "...",
      "error": null
    },
    {
      "success": true,
      "url": "https://www.youtube.com/watch?v=ok2",
      "page_id": "...",
      "error": null
    }
  ]
}
```

---

## 4) Create receipts from image

### Endpoint

`POST /api/v1/receipts`

### Content-Type

`multipart/form-data`

### Request

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/receipts" \
  -H "Authorization: Bearer $INTERNAL_API_TOKEN" \
  -H "X-Source: telegram-bot" \
  -H "X-Source-Message-Id: upd-3001" \
  -H "X-Source-User-Id: user-99" \
  -H "Idempotency-Key: telegram:chat42:upd-3001" \
  -F "receipt_image=@/absolute/path/to/receipt.jpg" \
  -F "store_hint=Falabella" \
  -F "batch_category=Groceries" \
  -F "request_id=telegram:chat42:upd-3001"
```

### Response (201)

```json
{
  "status": "ok",
  "items_count": 1,
  "items": [
    {
      "date": "03/07/2026",
      "category": "Groceries",
      "store": "Falabella",
      "product": "Milk",
      "quantity": 2,
      "price": 2.5
    }
  ],
  "sheets": {
    "status": "sent",
    "target_url": "https://script.google.com/macros/s/.../exec",
    "rows_received": 1,
    "request_id": "telegram:chat42:upd-3001",
    "upstream_status_code": 200,
    "upstream_response": {
      "ok": true,
      "inserted": 1
    }
  }
}
```

---

## 5) Create manual receipt entries (JSON)

### Endpoint

`POST /api/v1/receipts/manual`

### Content-Type

`application/json`

### Request

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/receipts/manual" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $INTERNAL_API_TOKEN" \
  -H "X-Source: telegram-bot" \
  -H "X-Source-Message-Id: upd-3002" \
  -H "X-Source-User-Id: user-99" \
  -H "Idempotency-Key: telegram:chat42:manual-upd-3002" \
  -d '{
    "date": "2026-03-24",
    "category": "Others",
    "store": "MercadoLibre",
    "items": [
      {"product": "Keyboard X", "quantity": 1, "price": 400000}
    ],
    "request_id": "telegram:chat42:manual-upd-3002"
  }'
```

### Response (201)

```json
{
  "status": "ok",
  "items_count": 1,
  "items": [
    {
      "date": "2026-03-24",
      "category": "Others",
      "store": "MercadoLibre",
      "product": "Keyboard X",
      "quantity": 1,
      "price": 400000.0
    }
  ],
  "sheets": {
    "status": "sent",
    "target_url": "https://script.google.com/macros/s/.../exec",
    "rows_received": 1,
    "request_id": "telegram:chat42:manual-upd-3002",
    "upstream_status_code": 200,
    "upstream_response": {
      "ok": true
    }
  }
}
```

---

## 6) Create Japanese study asset

### Endpoint

`POST /api/v1/study-assets/japanese`

### Request

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/study-assets/japanese" \
  -H "Authorization: Bearer $INTERNAL_API_TOKEN" \
  -H "X-Source: discord-bot" \
  -H "X-Source-Message-Id: msg-2001" \
  -H "X-Source-User-Id: user-77" \
  -H "Idempotency-Key: discord:g:c:msg-2001" \
  -F "image=@/path/to/study-image.png;type=image/png" \
  -F "note=for future manual anki cards"
```

Request contract (`multipart/form-data`):

- `image` (required file): `image/jpeg` or `image/png`
- `note` (optional text)

### Response (201)

```json
{
  "status": "ok",
  "page_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "language": "japanese",
  "asset_id": "20260324-120000-abc123",
  "title": "JP Asset 20260324-120000-abc123"
}
```

Behavior:

- API always sets Notion `Status` to `Pending`.
- API generates a readable unique title/id and stores it in Notion `Title`.
- API uploads image bytes to Notion File Upload API and attaches returned `file_upload` id in `Image`.
- API creates a new page for each request (no DB-level upsert key required).
- Optional `note` is saved to Notion `Note` (rich text).
- API sets Notion `Added at` using the configured business timezone date (same strategy as videos).

Expected Japanese DB schema:

- `Title`: title
- `Image`: files
- `Status`: select (service currently forces `Pending`)
- `Note`: rich_text
- `Added at`: date

---

## Idempotency Replay Behavior

If the same `Idempotency-Key` is sent again for the same source and endpoint within TTL:

- API returns the same JSON response
- with header: `X-Idempotency-Replayed: true`

---

## Common Errors

### 401 Unauthorized

Returned when `Authorization` is missing/invalid.

```json
{
  "detail": "Unauthorized"
}
```

### 429 Too Many Requests

Returned when per-endpoint/source limit is exceeded.

Headers include:

- `Retry-After: <seconds>`

Body:

```json
{
  "detail": "Rate limit exceeded"
}
```

### 400 Bad Request

Returned for input validation or missing required business config.

### 422 Unprocessable Entity

Returned when request schema validation fails (e.g., missing required file field).

Supported upload content types for `receipt_image`:

- `image/jpeg`
- `image/png`

If your source file is HEIC/HEIF, convert it in the bot/client before sending.

Optional `batch_category` values:

- `Groceries`
- `Pharmacy`
- `Transport`
- `Utilities`
- `Subscriptions`
- `Debt`
- `Leisure`
- `Others`

If `batch_category` is provided, it overrides per-item category from OCR.

Quantity behavior:

- `quantity` preserves decimal values for weighted products.
- Examples: `0.335`, `0.714`, `1.5`.

Price behavior:

- Price is normalized as COP whole units.
- Example normalization: `2.95 -> 2950` (OCR decimal misread of `2.950`).

### 502 Bad Gateway

Returned for upstream integration failures (Notion/Ollama/extractors).

YouTube extractor note:

- Videos extraction mode is controlled by `VIDEO_EXTRACTOR_MODE`:
  - `hybrid` (recommended): YouTube Data API primary, yt-dlp fallback
  - `youtube_api`: YouTube Data API only
  - `yt_dlp`: yt-dlp only
- For YouTube Data API modes, set `YOUTUBE_API_KEY`.
- If batch/single video returns failures containing `Sign in to confirm you're not a bot`, YouTube is blocking anonymous metadata extraction for your IP/session pattern.
- Configure `YTDLP_COOKIE_FILE` with a valid exported browser cookies file (Netscape format) so `yt-dlp` can access metadata.
