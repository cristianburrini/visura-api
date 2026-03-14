# Massive Visure Submission API (Agent MVP)

This document provides a concise overview of the massive submission API for AI agents.

## Base URL
`http://memory-proxy:8000` (within Docker) or `http://localhost:8000` (local)

## Core Concepts
- **Targets**: A list of property identifiers (foglio, particella) or owner identifiers (subalterno).
- **Scenarios**:
  - `1`: Batch property searches.
  - `2`: Batch owner searches.
  - `3`: Combined (Property Search -> Automatic Owner Search for all results).
- **Status**: `pending` -> `submitted` -> `done` | `error`.

## Endpoints

### 1. Schedule Massive Request
`POST /massive/schedule`

**Body:**
```json
{
  "scenario": 1|2|3,
  "provincia": "string",
  "comune": "string",
  "targets": [
    {"foglio": "string", "particella": "string", "sezione": "optional", "subalterno": "optional"}
  ],
  "tipo_catasto": "F"|"T"|null
}
```
**Response:** `{"scheduled": N, "skipped": M, "message": "..."}`

### 2. Check Queue Status
`GET /massive/status`

**Response:**
```json
{
  "queue_stats": {"pending": 10, "submitted": 2, "done": 100, "error": 1},
  "last_completed": [{"id": 1, "target": "10/100", "time": "ISO-TIMESTAMP"}]
}
```

### 3. Retrieve Results
Results are persisted in the related relational tables (`immobili`, `soggetti`, `titolarita`) and available through standard proxy endpoints.

## Best Practices
- **Duplicates**: The API automatically skips targets already in the queue or cache.
- **Polling**: Use `/massive/status` to monitor overall progress instead of individual polling for large batches.
- **Validation**: Ensure `provincia` and `comune` match the catalog names (use `/catalog/comuni` to verify).
