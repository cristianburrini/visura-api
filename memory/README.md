# Visure Memory Proxy

A lazy-loading, caching proxy for the Visure API. It serves as a drop-in replacement that stores results in a normalized PostgreSQL or MySQL database to speed up performance and reduce upstream scraper load.

## Features

- **Drop-in Replacement**: Implements the same API as `visure-api`.
- **Lazy Loading**: Fetches from upstream only on cache misses or expirations.
- **Normalised Schema**: Stores data in `immobili`, `soggetti`, and `titolarita` tables for direct SQL access.
- **Multi-Dialect**: Supports PostgreSQL and MySQL via SQLAlchemy.
- **Resilient**: Operates in "degraded mode" (serving expired cache) if the upstream is down.
- **Manual Control**: Endpoint to manually delete specific cache entries.

## Configuration

The proxy is configured via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | SQLAlchemy connection string (Postgres/MySQL) | `postgresql://appuser:apppass@localhost:5432/visura_cache` |
| `UPSTREAM_API_URL` | URL of the original `visure-api` | `http://visure-api:8000` |
| `CACHE_EXPIRATION_DAYS` | Number of days before a record is re-fetched | `365` |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, etc.) | `INFO` |

## Installation & Running

The proxy setup is modularised to allow running components separately or together for testing.

### 1. Manual Testing Environment (Proxy + DB)
To spin up both the proxy and a local PostgreSQL instance:
```bash
cd memory
docker compose up -d
```
This uses the default `docker-compose.yml` which combines the proxy and database definitions using `extends`.

### 2. Running Components Separately

#### Run only the PostgreSQL Database:
If you just need the database container:
```bash
docker compose -f docker-compose.db.yml up -d
```
Container name: `visura-memory-db`

#### Run only the Memory Proxy:
If you already have a database running (local or remote), configure `DATABASE_URL` and run:
```bash
docker compose -f docker-compose.proxy.yml up -d
```
Container name: `visura-memory-proxy`

### 3. Manual Initialisation
The proxy automatically initialises the database schema on its first startup.

## Behavior and Usage

### Flow
1. **Request**: Client sends `POST /visura` with parameters.
2. **Cache Check**: Proxy calculates a hash of the parameters. 
   - If a valid `completed` entry exists, it returns a `proxy_xxxx` ID immediately.
   - If not, it requests the visura from the upstream API and returns a `proxy_xxxx` ID once it has the upstream's `request_id`.
3. **Polling**: Client polls `GET /visura/proxy_xxxx`.
   - The proxy polls the upstream API on behalf of the client if the data isn't ready locally.
   - Once the upstream completes, the proxy parses the results, populates the normalized database tables, and returns the data.

### Degraded Mode
If the `UPSTREAM_API_URL` is unreachable:
- Existing `completed` results are still served, even if they have exceeded the `CACHE_EXPIRATION_DAYS` (marked as Degraded in logs/messages).
- New requests will fail with a `503 Service Unavailable` until the upstream is restored.

### Supported Endpoints
- `POST /visura`
- `POST /visura/intestati`
- `GET /visura/{proxy_id}`
- `DELETE /cache/{proxy_id}` (Manual invalidation)

## Database Access & Schema

The proxy stores normalized data in a relational format. You can connect to the database directly for advanced queries or report generation.

### Connection Parameters
If running via the default `docker compose up`:
- **Host**: `localhost`
- **Port**: `5433`
- **Database**: `visura_cache`
- **User**: `appuser`
- **Password**: `apppass`

### Connecting via CLI
```bash
psql -h localhost -p 5433 -U appuser -d visura_cache
```

### Schema Overview
- `immobili`: General property info (foglio, mappale, sub, categoria, rendita).
- `soggetti`: Owners/Entities.
- `titolarita`: Mapping between subjects and properties (rights, percentages).
- `visura_cache`: Raw JSON responses index.

### Useful SQL Commands
- **List Tables**: `\dt`
- **Inspect Column Types**: `\d+ immobili`
- **Query Recent Assets**: `SELECT * FROM immobili ORDER BY id DESC LIMIT 5;`
