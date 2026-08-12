# FireScrapling

An API-first web scraping, crawling and mapping engine that turns any URL into
LLM-ready Markdown or structured JSON. FastAPI backend, React dashboard, one
`docker compose up`.

```
                 ┌──────────────────────────┐
  browser  ────► │ nginx (frontend :8080)   │
                 │  • React SPA (Vite)      │
                 │  • /v1/* → backend       │
                 └───────────┬──────────────┘
                             │
                 ┌───────────▼──────────────┐
                 │ FastAPI (backend :8000)  │
                 │  api_server.py  routes   │
                 │  api_auth.py    keys/RL  │
                 │  security_url.py SSRF    │
                 │  main.py        jobs     │
                 │  scraping_engine.py      │
                 └───────────┬──────────────┘
                             │
              ┌──────────────┼───────────────┐
        SQLite (jobs,   file cache      Playwright /
        keys, usage)    (data/cache)    scrapling fetcher
```

## Quickstart

```bash
cp .env.example .env          # then edit: OPENROUTER_API_KEY is optional
docker compose up --build
```

- Dashboard → http://localhost:8080
- API → http://localhost:8000 (docs at `/docs`)

Local dev without Docker:

```bash
# backend
cd apps/firescrapling/backend
pip install -r requirements.txt && playwright install chromium
uvicorn api_server:app --reload --port 8000

# frontend (proxies /v1 and /health to :8000, see vite.config.ts)
cd apps/firescrapling/frontend
npm install && npm run dev
```

## API tour

Authenticate with an API key: `Authorization: Bearer fs_…` (or `X-API-Key`).
Keys are created from the dashboard, or via `POST /v1/keys` with a session token
from `POST /v1/auth/login`.

| Endpoint | Purpose |
|---|---|
| `POST /v1/scrape` | Single page → `markdown`, `html`, `raw_content`, `links`, `images`, `screenshot`, or schema-driven `llm_extraction`. Supports browser `actions`, `async`, and webhooks. |
| `POST /v1/crawl` | Async BFS crawl of a domain (`limit`, `maxDepth`, `ignoreSubdomains`) → `202` + job id |
| `GET /v1/crawl/{id}` | Crawl status + per-page results |
| `POST /v1/map` | Fast link discovery (page links + `sitemap.xml`), optional `search` filter |
| `GET /v1/jobs`, `GET /v1/jobs/{id}` | Job history and status |
| `GET /v1/jobs/{id}/stream` | Live logs as SSE or NDJSON (`?format=ndjson`) |
| `POST /v1/auth/register\|login\|logout` | Account + session tokens |
| `GET/POST/DELETE /v1/keys` | API key lifecycle (full value shown once) |
| `POST /v1/playground/scrape\|map\|crawl` | Anonymous homepage demo, IP rate-limited |
| `GET /health`, `GET /health/ready` | Liveness / readiness |

```bash
curl -X POST http://localhost:8000/v1/scrape \
  -H "Authorization: Bearer $FIRESCRAPLING_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","formats":["markdown"],"onlyMainContent":true}'
```

Every request carries `X-Request-ID` and `X-RateLimit-*` headers; errors are
`{"error": {"code", "message", "request_id"}}`. `POST /v1/scrape|crawl` accept an
`Idempotency-Key` header. Webhook payloads are signed with
`X-FireScrapling-Signature: sha256=<hmac>` and retried with backoff.

## Configuration

All variables live in the root `.env` (see [.env.example](.env.example)).

| Variable | Default | Purpose |
|---|---|---|
| `CORS_ORIGINS` | `http://localhost:8080,…` | Allowed browser origins |
| `API_REQUIRE_AUTH` | `true` | Require an API key on `/v1/scrape|crawl|map` |
| `API_ALLOW_PRIVATE_URLS` | `false` | Allow localhost/private IP targets (dev only) |
| `RATE_LIMIT_PER_MINUTE` | `60` | Per-key sliding window |
| `SCRAPE_CACHE_TTL` | `3600` | Response cache TTL, seconds |
| `PLAYGROUND_ENABLED` | `true` | Public no-auth demo endpoints |
| `PLAYGROUND_RATE_LIMIT_PER_MINUTE` | `8` | Per-IP playground limit |
| `PLAYGROUND_MAP_MAX_LINKS` / `_CRAWL_LIMIT` / `_RESULT_PREVIEW_CHARS` | `40` / `3` / `12000` | Playground caps |
| `OPENROUTER_API_KEY` | — | Enables `schema` structured extraction |
| `OPENROUTER_MODEL` | `google/gemini-2.0-flash-001` | Extraction model |

## Engine notes

- **Main content** via trafilatura (`onlyMainContent`), falling back to full-page markdownify.
- **Crawling** is BFS with URL normalisation + dedup, `robots.txt` compliance,
  politeness delay with jitter, and same-site / eTLD+1 scope rules.
- **Fetching** uses `scrapling`'s stealth `Fetcher` with bounded retries and backoff on
  5xx/429; Playwright is used when browser `actions` or `screenshot` are requested.
- **SSRF protection**: loopback, RFC1918, link-local and unique-local targets are refused
  unless explicitly allowed.
- **Caching**: SHA-256 keyed file cache varying on URL + `onlyMainContent` + formats.

## Status

Production-ready: the extraction engine, the REST API, auth/keys, rate limiting,
idempotency, webhooks, job streaming.

Known gaps (tracked in [docs/plan/](docs/plan/) and [ROADMAP.md](ROADMAP.md)):

- Parts of the dashboard (Overview, Admin, Webhooks, Usage) still render placeholder data.
- Jobs run in in-process threads, not a durable queue; storage is SQLite.
- No credits/billing layer yet.

## Repo layout

```
apps/firescrapling/backend    FastAPI app + scraping engine
apps/firescrapling/frontend   React + Vite + Tailwind + shadcn/ui dashboard
docs/                         Mintlify docs and improvement plans
docker-compose.yml            backend + nginx-served frontend
```
