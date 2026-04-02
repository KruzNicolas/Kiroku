# Kiroku API

Kiroku API is a FastAPI modular monolith that automates metadata extraction, AI-powered classification, and idempotent persistence of YouTube videos into Notion.

## 🚀 Features

- **Automated Metadata Extraction:** Safely extracts video title, channel name, tags, description, and game category using `yt-dlp`.
- **Cloud AI Classification:** Routes reasoning requests directly to the Ollama Cloud API, yielding high-accuracy output mapped to strict Notion schemas without requiring any local GPU or model hosting.
- **Single & Bulk API Processing:** Process a single URL or send batches through HTTP endpoints.
- **Smart Retries & Resilience:** Handles API rate-limits gracefully with exponential backoff (`tenacity`) for both the AI model and the Notion API.
- **Manual Priority Overrides:** Support for appending `high`, `medium`, `low`, or `later` next to a URL to bypass AI priority reasoning and forcefully push the video to a specific queue.
- **Added at Date:** Video entries include `Added at` based on configurable timezone (default `America/Bogota`).

## 📋 Prerequisites

1. **Python 3.11+**
2. **Ollama Cloud API Key** (Get yours at [ollama.com/settings/keys](https://ollama.com/settings/keys)).
3. **Notion Internal Integration** with a generated API Token and a properly shared Notion Database. The database must have a `Channel` property (Text) configured.

## 🛠 Setup

1. **Clone the repository:**
   ```bash
   git clone git@github.com:KruzNicolas/Kiroku.git
   cd Kiroku
   ```

2. **Set up the virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables:**
   Copy the example config and fill in your credentials:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` to include your exact `NOTION_TOKEN`, `NOTION_DATABASE_ID_VIDEOS`, `NOTION_DATABASE_ID_STUDY_ASSETS_JAPANESE`, `OLLAMA_API_KEY`, `OLLAMA_MODEL_VIDEO`, and `OLLAMA_MODEL_RECEIPTS`.

   Receipts -> Google Sheets integration:
   - `RECEIPTS_GOOGLE_SHEETS_URL=<your_apps_script_web_app_url>`
   - `RECEIPTS_GOOGLE_SHEETS_API_TOKEN=<POST_API_TOKEN_from_script_properties>`

   Optional video date timezone config:
   - `VIDEOS_ADDED_AT_TIMEZONE=America/Bogota`
   - `YTDLP_COOKIE_FILE=/absolute/path/to/youtube_cookies.txt` (recommended when YouTube anti-bot blocks metadata extraction)
   - `YOUTUBE_API_KEY=<your_google_api_key>`
   - `YOUTUBE_API_BASE_URL=https://www.googleapis.com/youtube/v3`
   - `VIDEO_EXTRACTOR_MODE=hybrid` (`hybrid` = YouTube API primary + yt-dlp fallback)

   Bot gateway hardening config:
   - `INTERNAL_API_TOKEN=<strong-random-token>`
   - `IDEMPOTENCY_TTL_SECONDS=86400`
   - `RATE_LIMIT_VIDEOS_PER_MIN=20`
   - `RATE_LIMIT_VIDEOS_BATCH_PER_MIN=10`
   - `RATE_LIMIT_RECEIPTS_PER_MIN=5`
   - `RATE_LIMIT_STUDY_ASSETS_JP_PER_MIN=15`

## 💻 API Usage

For full request/response contracts (headers, error cases, payload examples), see:

- [`API_ENDPOINTS_GUIDE.md`](./API_ENDPOINTS_GUIDE.md)

### Start the API

```bash
uvicorn app.main:app --reload
```

### 1. Health check

```bash
curl -X GET "http://127.0.0.1:8000/health"
```

### 2. Create one video record

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/videos" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.youtube.com/watch?v=...", "manual_priority":"later"}'
```

### 3. Create videos in batch

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/videos/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {"url": "https://www.youtube.com/watch?v=..."},
      {"url": "https://www.youtube.com/watch?v=...", "manual_priority": "low"}
    ],
    "max_workers": 3
  }'
```

Batch response includes `failed_urls` to quickly identify links that could not be persisted.

### 4. Create receipt entries from image

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/receipts" \
  -F "receipt_image=@/absolute/path/to/receipt.jpg" \
  -F "store_hint=Falabella" \
  -F "batch_category=Groceries" \
  -F "request_id=telegram:chat42:update9001"
```

Response returns line-item headers without `batch_id` and includes Google Sheets POST result.

Receipts endpoint accepts `image/jpeg` and `image/png` only.
If your source is HEIC/HEIF (common on iPhone), convert it to JPEG in the bot/client before sending.

Date note for receipts pipeline:
- OCR may infer dates in slash format, but Google Sheets upstream expects `YYYY-MM-DD`.
- The API now normalizes common date formats before POSTing to Apps Script.

Category note for receipts pipeline:
- OCR still extracts item category, but `batch_category` can override all items in the current receipt.
- Allowed values: `Groceries`, `Pharmacy`, `Transport`, `Utilities`, `Subscriptions`, `Debt`, `Leisure`, `Others`.

Quantity note for receipts pipeline:
- Quantity keeps decimal values for weighted products (e.g., `0.714`, `0.335`).

Price note for receipts pipeline:
- Receipts are handled as COP whole units.
- If OCR returns small decimal values (e.g., `2.95` for `2.950`), API normalizes to `2950` before sending to spreadsheet.

### 5. Create manual receipt entries (small purchases)

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/receipts/manual" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-03-24",
    "category": "Others",
    "store": "MercadoLibre",
    "items": [
      {"product": "Keyboard X", "quantity": 1, "price": 400000}
    ],
    "request_id": "telegram:chat42:manual9001"
  }'
```

### 6. Create Japanese study asset (manual workflow)

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/study-assets/japanese" \
  -F "image=@/path/to/study-image.jpg;type=image/jpeg" \
  -F "note=for future manual anki cards"
```

This endpoint now expects `multipart/form-data`.

- `image` is required and accepts `image/jpeg` or `image/png`.
- `note` is optional text.
- API sets Notion `Status` to `Pending` and auto-generates a readable unique `Title`.
- API uploads binary image bytes through Notion File Upload API and attaches it to `Image` as `file_upload`.
- API creates a new page for each request (no module upsert key required).
- API also sets `Added at` using the same timezone-based date strategy as videos (`VIDEOS_ADDED_AT_TIMEZONE`, default `America/Bogota`).

Expected Notion properties for Japanese DB:

- `Title` (title)
- `Image` (files)
- `Status` (select)
- `Note` (rich_text)
- `Added at` (date)

## 🧪 Test Write Mode (optional)

If you run real API calls against your Notion database and want to identify test records quickly:

- set `APP_TEST_WRITE_MODE=true`
- if confidence would be `>= 0.8`, the API forces it to `0.79`

Disable it with `APP_TEST_WRITE_MODE=false`.

## 🔐 Bot-Only API Access

All `/api/v1/*` endpoints now require:

- `Authorization: Bearer <INTERNAL_API_TOKEN>`
- `X-Source` (recommended: `discord-bot` or `telegram-bot`)
- `Idempotency-Key` (recommended for retry-safe writes)

Optional audit headers:

- `X-Source-Message-Id`
- `X-Source-User-Id`

## 🏗 Architecture & Spec-Driven Development
This project follows Spec-Driven Development (SDD), enforcing strong typings (`pydantic`), interface contracts, and modular layers (`api`, `application`, `domain`, `infrastructure`, `shared`).

## 🏗 Architecture & Migration Status

- FastAPI modular monolith structure is active under `app/`.
- The `videos` module is migrated and exposed via API.
- Notion persistence is centralized in `app/shared/notion/save_layer.py`.
- Module-owned DB id is configured through `NOTION_DATABASE_ID_VIDEOS`.

### API Endpoints

- `GET /health`
- `POST /api/v1/videos`
- `POST /api/v1/videos/batch`
- `POST /api/v1/receipts`
- `POST /api/v1/receipts/manual`
- `POST /api/v1/study-assets/japanese`

### Run FastAPI locally

```bash
uvicorn app.main:app --reload
```

### Important migration constraint

No Docker/container/cloud infrastructure changes are part of this migration stage.

## ✅ Testing

Run tests with:

```bash
pytest
```

Current test coverage includes:
- API endpoint contract tests (`/health`, `/videos`, `/videos/batch`) with dependency overrides.
- Videos service unit tests for single processing, bulk processing, and validation errors.
- Receipts API/service tests for OCR extraction contracts.
- Study assets API/service tests for Japanese image uploads to Notion.
