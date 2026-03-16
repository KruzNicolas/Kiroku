# Kiroku CLI

Kiroku CLI is a powerful command-line tool that automates the ingestion, metadata extraction, and AI-powered classification of YouTube links directly into a structured Notion database. 

It uses `yt-dlp` to extract clean metadata without downloading media, and leverages a hybrid AI architecture (Ollama + MiniMax 2.5) to categorize videos strictly into designated learning/watch queues.

## 🚀 Features

- **Automated Metadata Extraction:** Safely extracts video title, tags, description, and game category using `yt-dlp`.
- **Hybrid AI Classification:** Routes reasoning requests through a local Ollama endpoint to MiniMax 2.5, yielding high-accuracy output mapped to strict Notion schemas.
- **Single & Bulk Processing:** Process a single URL immediately or feed it a `.txt` file to process hundreds of URLs concurrently.
- **Smart Retries & Resilience:** Handles API rate-limits gracefully with exponential backoff (`tenacity`) for both the AI model and the Notion API.
- **Manual Overrides:** Support for appending a `later` keyword next to a URL to bypass AI priority and forcefully push the video to your backlog.

## 📋 Prerequisites

1. **Python 3.11+**
2. **Ollama** running locally with the model configured (e.g., `minimax-m2.5:cloud`).
3. **Notion Internal Integration** with a generated API Token and a properly shared Notion Database.

## 🛠 Setup

1. **Clone the repository:**
   ```bash
   git clone git@github.com:KruzNicolas/Kiroku-cli.git
   cd Kiroku-cli
   ```

2. **Set up the virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables:**
   Copy the example config and fill in your Notion credentials:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` to include your exact `NOTION_TOKEN` and `NOTION_DATABASE_ID`.

## 💻 Usage

We provide an easy-to-use script (`run.sh`) that automatically activates your environment and handles the commands.

### 1. Process a Single URL
```bash
./run.sh url "https://www.youtube.com/watch?v=..."
```

**Force the priority to "Later":**
If you want to skip AI priority reasoning and push it straight to your backlog, append `later` to the URL string:
```bash
./run.sh url "https://www.youtube.com/watch?v=... later"
```

### 2. Process Bulk URLs from a File
Create a text file (e.g., `links.txt`) with one URL per line. Blank lines and comments (starting with `#`) are ignored.
```bash
./run.sh file links.txt
```

**Custom Concurrency:**
You can specify the number of parallel workers (default is 3) to process files faster. Beware of YouTube/Notion rate limits.
```bash
./run.sh file links.txt 5
```

## 🏗 Architecture & Spec-Driven Development
This project was developed strictly adhering to Spec-Driven Development (SDD), enforcing strong typings (`pydantic`), interface contracts, and single-responsibility architectural layers (`extractor`, `inferencer`, `notion_writer`).
