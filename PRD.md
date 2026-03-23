# PRD: Media Classification Tool

> Automate classification of YouTube links into a structured Notion database using yt-dlp metadata and Hybrid AI inference.

**Version**: 0.1.0-draft  
**Author**: Nicolas Romero  
**Date**: 2026-03-15  
**Status**: Draft

---

## 1. Project Overview

The Media Classification Tool automates ingestion and categorization of YouTube URLs into a Notion database. It supports both single-link processing and bulk processing from text files, then classifies each item with high accuracy using a Hybrid AI architecture:

- Local orchestration through Ollama on localhost
- Cloud reasoning by MiniMax 2.5 for final Category and Priority decisions

The objective is a reliable, repeatable pipeline that transforms raw links into actionable, prioritized learning/watch queues.

---

## 2. Goals and Scope

### 2.1 Goals

1. Accept YouTube links in single and bulk modes.
2. Extract only relevant metadata using yt-dlp.
3. Produce one strict Category and one strict Priority per link.
4. Persist records to a Notion database with deterministic schema mapping.
5. Handle invalid URLs, rate limits, and transient failures safely.

### 2.2 Out of Scope

1. Uploading or downloading media content.
2. Collecting uploader profile info, duration, view counts, likes, or comments.
3. Human-in-the-loop moderation UI in v1.

---

## 3. System Workflow

Mandatory end-to-end flow:

**Input -> Metadata Extraction (yt-dlp) -> Local Request (Ollama) -> Intelligence (MiniMax 2.5) -> Notion API**

### 3.1 Runtime Sequence

1. Receive URL input via API request body (single input string or bulk inputs array), supporting optional inline manual token `later` (example: `https://youtube.com/... later`).
2. Validate URL format and deduplicate.
3. Run yt-dlp metadata extraction for each valid URL.
4. Build normalized inference payload.
5. Send request to local Ollama endpoint.
6. Ollama routes reasoning request to MiniMax 2.5 (cloud model).
7. MiniMax 2.5 returns strict JSON: `{ category, priority, rationale, confidence }`.
8. Apply manual override rule: if input contains trailing `later`, force final Priority to `Later` and bypass AI priority suggestion.
9. Create or update Notion page with strict database properties and write AI rationale in the page body.
10. Print real-time execution logs to terminal for each stage (no log files persisted).

---

## 4. Input Modes

### 4.1 Single Mode

- Accept one URL via API request body input string.
- Support optional manual marker `later` next to URL to force Priority `Later`.
- Process immediately.
- Return structured classification output and Notion write status.

### 4.2 Bulk Mode

- Accept `.txt` file path.
- One URL per line; blank lines and comments (optional `#`) are ignored.
- Support optional manual marker `later` per line (example: `https://youtube.com/... later`).
- Process with bounded concurrency and retry policy.
- Provide batch summary: total, succeeded, failed, skipped duplicates.

---

## 5. Metadata Extraction (yt-dlp)

The system MUST extract only the following fields:

1. **Title**
2. **Description**
3. **Metadata Tags** (video tags/keywords)
4. **Game Category** (if present in source metadata)

The system MUST NOT collect or persist:

1. Uploader/channel info
2. Duration
3. View count and social metrics

### 5.1 Normalized Payload (Pre-AI)

```json
{
  "url": "https://youtube.com/watch?v=...",
  "title": "...",
  "description": "...",
  "tags": ["...", "..."],
  "game_category": "Valorant"
}
```

---

## 6. AI Inference Architecture

### 6.1 Orchestration Layer

- All classification requests are sent to Ollama running on localhost.
- Ollama acts as local gateway, prompt assembler, and response normalizer.

### 6.2 Reasoning Layer

- Ollama is configured to use **MiniMax 2.5 (Cloud)** for reasoning.
- MiniMax 2.5 is the authoritative decision engine for:

1. `Category` selection (strict 1-of-6)
2. `Priority` selection (strict 1-of-4)

### 6.3 Output Contract

Model output MUST conform to strict machine-parseable JSON:

```json
{
  "category": "Dev | Maths | Valorant | Leisure | Talks | 日本語",
  "priority": "High | Medium | Low | Later",
  "rationale": "short explanation",
  "confidence": 0.0
}
```

Interpretation rules:

1. `priority` is the AI suggestion.
2. Final persisted Priority may be overridden to `Later` when manual token `later` is present in input.
3. `rationale` is stored in the Notion page body (not as a database property).
4. `confidence` is stored in Notion property `Confidence` (Number).

If output is malformed, the orchestrator retries once with a JSON-repair prompt. If still invalid, record failure and continue batch.

---

## 7. Classification Framework (Strict Tags)

Category is a required single-select property with only these values:

1. **日本語**: Japanese studies (Kanji, Anki, grammar, exam preparation).
2. **Dev**: Software engineering, automation, blockchain, backend, data (science/engineering), and new AI/tech tools.
3. **Maths**: Pure mathematics or university-level academic content.
4. **Valorant**: Tactical gameplay/content specifically about Valorant.
5. **Leisure**: General gameplays, entertainment, and non-essential chill content.
6. **Talks**: Video essays, podcasts, long-form commentary/background content.

---

## 8. Priority Logic (Strict Levels)

Priority is a required single-select property with only these values:

1. **High**: Hot content (new AI tools, urgent programming/data news, immediate workflow gains).
2. **Medium**: Important long-term growth content (math, system design, data) without urgency.
3. **Low**: General entertainment, gameplays, or casual leisure.
4. **Later**: Background talks, long essays, watch-later backlog.

### 8.1 Manual Override Rule

If the keyword `later` appears next to a URL in input, the system MUST:

1. Set final Priority to `Later`.
2. Bypass AI priority suggestion for that URL.
3. Keep AI category inference active.

---

## 9. Functional Requirements

### 9.1 Core Requirements

- **FR-001**: System MUST support single URL processing via argument/string.
- **FR-002**: System MUST support bulk `.txt` processing with one URL per line.
- **FR-003**: System MUST extract only title, description, tags, and game category via yt-dlp.
- **FR-004**: System MUST use Ollama localhost as the only inference entry point.
- **FR-005**: System MUST delegate reasoning decisions to MiniMax 2.5.
- **FR-006**: System MUST write results to Notion using strict schema mapping.
- **FR-007**: System MUST enforce strict category and priority vocabularies.
- **FR-010**: Notion database properties MUST be strictly limited to: `Title`, `Category`, `Priority`, `URL`, `Confidence`.
- **FR-011**: AI rationale MUST be written to the Notion page body content, not to a database property.
- **FR-012**: Confidence MUST be written to property `Confidence` as Number.
- **FR-013**: If input includes keyword `later` next to URL, final Priority MUST be forced to `Later`.
- **FR-014**: The API MUST emit structured request logs for each processing stage.
- **FR-015**: The tool MUST NOT persist logs to disk.

### 9.2 Disambiguation Logic (Game Category + Tags)

The classifier MUST combine `game_category`, `tags`, `title`, and `description` signals to separate close classes:

- **Valorant vs Leisure**:

1. If `game_category` explicitly indicates Valorant, strongly bias to `Valorant`.
2. If tags/title include tactical shooter terms (`valorant`, `vct`, `radiant`, `immortal`, `aim routine`) and gameplay context, classify as `Valorant`.
3. If game-related but non-Valorant and primarily entertainment/chill, classify as `Leisure`.

- **Talks vs Leisure**:

1. If metadata indicates podcast, essay, commentary, interview, analysis, or long-form background content, classify as `Talks`.
2. If content is primarily gameplay/entertainment without essay/podcast structure, classify as `Leisure`.

- **Dev / Maths / 日本語 precedence**:

1. If metadata clearly maps to technical/software/data topics, prioritize `Dev` over entertainment classes.
2. If metadata is explicit for academic mathematics, prioritize `Maths`.
3. If metadata is explicit for Japanese study workflows (kanji, grammar, JLPT, Anki), prioritize `日本語`.

### 9.3 Determinism and Idempotency

- **FR-008**: Duplicate URLs MUST not create duplicate Notion records (upsert by URL).
- **FR-009**: Reprocessing the same URL SHOULD update category/priority only when model output changes.

---

## 10. Notion Data Schema

Required Notion database mapping:

| Notion Property | Type   | Source                 | Required | Notes                                               |
| --------------- | ------ | ---------------------- | -------- | --------------------------------------------------- |
| `Title`         | Title  | `title`                | Yes      | Fallback to URL slug if title missing               |
| `Category`      | Select | AI output `category`   | Yes      | Strict 6-tag vocabulary                             |
| `Priority`      | Select | Final priority         | Yes      | AI output unless overridden by manual `later` token |
| `URL`           | URL    | input URL              | Yes      | Unique key for upsert                               |
| `Confidence`    | Number | AI output `confidence` | Yes      | Range 0.0 to 1.0                                    |

Page body content mapping:

1. AI `rationale` MUST be written to the Notion page body.
2. No additional database properties are allowed in v1.

---

## 11. Technical Considerations

### 11.0 Technical Stack

The implementation stack for v1 is:

1. **Python**: Primary language for API orchestration and pipeline execution.
2. **HTTP Request to Ollama localhost**: Local API calls to Ollama endpoint for model inference routing to MiniMax 2.5.
3. **yt-dlp**: Metadata extraction from YouTube URLs (title, description, tags, game category if available).
4. **notion-client**: Official Notion API SDK for creating/updating database entries and writing rationale into page body.
5. **python-dotenv**: Environment variable loading for local configuration and secret management (for example, Notion token).
6. **JSON**: Standard payload format for model request/response contracts and internal structured data handling.

Suggested runtime dependencies:

1. `python>=3.11`
2. `requests`
3. `yt-dlp`
4. `notion-client`
5. `python-dotenv`

### 11.1 Rate Limits

1. **yt-dlp/source constraints**:

- Apply bounded concurrency in bulk mode (configurable workers).
- Add jittered delays between requests when source rejects bursts.

2. **MiniMax 2.5 / cloud inference constraints**:

- Use request queue with max in-flight limit.
- Retry transient `429/5xx` with exponential backoff.

3. **Notion API constraints**:

- Respect Notion per-integration rate limits.
- Batch writes with throttling and retry policy.

### 11.2 Error Management (Invalid Links and Failures)

- Validate URL format before processing.
- For invalid or inaccessible links, mark record as `failed` with reason.
- Continue processing remaining links in bulk mode (no full-batch abort).
- Emit structured request logs per URL: stage, error code, retry count.
- Emit final batch report with actionable failures.

### 11.3 API Observability and Logging

The API MUST expose real-time structured logs for each request, for example:

1. `[INFO] Extracting metadata for: [URL]...`
2. `[INFO] Metadata enriched (Tags & Category found).`
3. `[INFO] Requesting classification from MiniMax 2.5 (via Ollama)...`
4. `[INFO] AI Confidence: 0.92. Rationale received.`
5. `[SUCCESS] Entry created in Notion: [Video Title].`

Logging policy:

1. Logs are emitted to process stdout for run-time feedback.
2. The tool MUST NOT save logs to files or external storage.

### 11.4 Reliability Safeguards

1. Stage-level retries (extract, infer, write).
2. Dead-letter output file for unresolved URLs.
3. Idempotent upsert into Notion by URL.
4. Timeout budgets per stage to avoid blocked workers.

---

## 12. Non-Functional Requirements

1. **Accuracy**: Category and Priority consistency target >= 90% on validation set.
2. **Performance**: Single URL processing target < 8s median (network dependent).
3. **Scalability**: Bulk mode should process at least 500 URLs per run without manual intervention.
4. **Observability**: Real-time structured logs and per-stage run metrics are required.
5. **Security**: API keys stored in environment variables; never persisted in logs.
6. **Logging Privacy**: No persistent log files are created.

---

## 13. Acceptance Criteria

1. User can run single mode and get one Notion row with valid Category/Priority.
2. User can run bulk mode on `.txt` and get summary of success/fail/skip counts.
3. Only approved metadata fields are extracted; Notion database stores only `Title`, `Category`, `Priority`, `URL`, and `Confidence`.
4. All inference requests go through Ollama localhost and are resolved by MiniMax 2.5.
5. Category and Priority values always match strict enums.
6. If input line includes `later` next to URL, final Priority is forced to `Later`.
7. AI rationale is written into Notion page body and confidence into `Confidence` property.
8. Real-time logs are visible in terminal, and no logs are persisted.
9. Invalid links and rate-limit events are handled without stopping entire batch.

---

## 14. Open Questions

1. Should `Talks` be auto-assigned to `Later` when confidence is high, or remain fully model-driven?
2. Do we require multilingual keyword dictionaries for Japanese/English/Spanish mixed metadata?
3. Should confidence below a threshold (for example < 0.60) trigger a `needs-review` state in Notion?
