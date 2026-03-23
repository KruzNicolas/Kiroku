# Kiroku API

Kiroku API is a FastAPI modular monolith that automates metadata extraction, AI-powered classification, and idempotent persistence of YouTube videos into Notion.

## 🚀 Features

- **Automated Metadata Extraction:** Safely extracts video title, channel name, tags, description, and game category using `yt-dlp`.
- **Cloud AI Classification:** Routes reasoning requests directly to the Ollama Cloud API, yielding high-accuracy output mapped to strict Notion schemas without requiring any local GPU or model hosting.
- **Single & Bulk API Processing:** Process a single URL or send batches through HTTP endpoints.
- **Smart Retries & Resilience:** Handles API rate-limits gracefully with exponential backoff (`tenacity`) for both the AI model and the Notion API.
- **Manual Priority Overrides:** Support for appending `high`, `medium`, `low`, or `later` next to a URL to bypass AI priority reasoning and forcefully push the video to a specific queue.

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
   Edit `.env` to include your exact `NOTION_TOKEN`, `NOTION_DATABASE_ID_VIDEOS`, and `OLLAMA_API_KEY`.

## 💻 API Usage

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

## 🧪 Test Write Mode (optional)

If you run real API calls against your Notion database and want to identify test records quickly:

- set `APP_TEST_WRITE_MODE=true`
- if confidence would be `>= 0.8`, the API forces it to `0.79`

Disable it with `APP_TEST_WRITE_MODE=false`.

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
