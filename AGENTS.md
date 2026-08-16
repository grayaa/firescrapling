# AGENTS.md

Context for AI assistants (Cursor, Claude Code, …) and new contributors working in this
repo. Keep it current — it is the fastest way to be useful here.

## What this is

FireScrapling: a scrape/crawl/map API that turns URLs into LLM-ready Markdown or
structured JSON, plus a React dashboard for accounts, API keys and usage.

```
apps/firescrapling/backend    FastAPI + the scraping engine (Python 3.11)
apps/firescrapling/frontend   React 18 + Vite + Tailwind + shadcn-style UI (TypeScript)
docs/                         Mintlify docs and the phased improvement plans
docker-compose.yml            redis, worker (RQ), backend :8000, frontend :8080
```

### Backend files, by responsibility

| File | Owns |
|---|---|
| `api_server.py` | All HTTP routes, request/response models, error envelope, CORS, request ids |
| `api_auth.py` | FastAPI dependencies: API-key auth, session auth, rate limiting |
| `main.py` | Business logic: accounts, keys, jobs, usage aggregation, job orchestration |
| `settings.py` | Env-driven config: Scrapfly, Redis, fetch provider, queue flags |
| `fetch_provider.py` | Pluggable fetch: Scrape.do, Scrapfly, or local scrapling |
| `fetch_strategy.py` | Credit-aware escalate: classify → tier ladder → domain profile cache |
| `job_queue.py` / `job_tasks.py` | Redis RQ enqueue + worker entrypoints (scrape/crawl/webhooks) |
| `scraping_engine.py` | Fetching, retries, markdown extraction, concurrent BFS crawl, robots, cache |
| `extractors/` + `media_extract.py` | Domain media extractors (manifest URLs only) |
| `billing.py` | Flat plans + Stripe checkout/webhook stubs |
| `security_url.py` | SSRF guard — validates every user-supplied target URL |
| `webhook_delivery.py` | HMAC-signed webhook POSTs with retry/backoff |

MCP (optional): `apps/firescrapling/mcp/` — FastMCP stdio tools over the HTTP API.

`api_server.py` imports `main` as `core`. Routes stay thin: validate, delegate to
`core`, shape the response.

### Frontend files

`src/restClient.ts` is the single place that talks to the API — add new calls there,
typed, rather than calling `fetch` from a component. `src/features/*` are page-level
views; `src/components/ui/*` are hand-rolled shadcn-style primitives (not the npm
package — check the file before assuming a prop like `asChild` exists).

## Commands

```bash
# Full stack (the realistic check)
docker compose up --build            # dashboard :8080, API :8000, /docs for Swagger

# Frontend
cd apps/firescrapling/frontend
npm install
npm run dev                          # :5173, proxies /v1 and /health to :8000
npm run typecheck                    # tsc --noEmit — run this before every commit
npm run build                        # typecheck + vite build

# Backend
cd apps/firescrapling/backend
pip install -r requirements.txt && playwright install chromium
uvicorn api_server:app --reload --port 8000
python scripts/run_scraping_tests.py # fixture-server checks, no network needed
```

## Conventions

- **Errors**: every API error is `{"error": {"code", "message", "request_id"}}`. Raise
  `HTTPException(status_code=…, detail={"code": …, "message": …})`; the handlers in
  `api_server.py` do the rest.
- **New endpoints**: add the route in `api_server.py`, the logic in `main.py`, the typed
  client function in `restClient.ts`, and keep `openapi.yaml` in sync (it is
  hand-maintained today — see the plan for generating it instead).
- **Two credentials, never mixed**: session tokens (from `/v1/auth/login`) authorize
  account routes — `/v1/keys`, `/v1/usage/summary` — via `get_session_user`. API keys
  (`fs_…`) authorize `/v1/scrape|crawl|map` via `get_api_context`. On the client, pass
  `auth: "session" | "key" | "none"` to `apiFetch`.
- **Every user-supplied URL** goes through `validate_request_url` before any fetch.
- **Comments** explain why, not what, and only where the reason isn't obvious.
- Match the surrounding style; the frontend uses uppercase tracking-widest labels and
  `cn()` for conditional classes.

## Gotchas (learned the hard way)

- **SQLite has one writer.** `main.py` helpers each open their own connection. If a job
  generator holds an open transaction and you call another helper that writes, you get
  `database is locked`. Commit before handing off. `busy_timeout` is set, but ordering is
  the real fix.
- **Don't reintroduce passlib.** It cannot drive bcrypt ≥ 4.1. `hash_password` /
  `verify_password` in `main.py` call bcrypt directly.
- **`npm run typecheck` catches real crashes**, not just type noise — missing icon
  imports in this codebase are `ReferenceError`s at render. Run it.
- **Jobs use Redis RQ** when `QUEUE_ENABLED` and Redis are available (`docker compose`
  runs `redis` + `worker`). Otherwise they fall back to daemon threads.
- **Paid fetch**: `SCRAPE_API_KEY` (Scrape.do, preferred in `auto`) or
  `SCRAPFLY_API_KEY`. Defaults are cheap (`render_js`/`asp` off); `FETCH_ESCALATE`
  probes local/static first and only enables JS/ASP/super/residential when needed.
  Force full power per request with `renderJs` / `asp` / `proxyPool`. See
  `GET /v1/capabilities`.
- The admin console is gated by `ADMIN_SECRET` (Bearer token on `/v1/admin/*`). Set it in
  `.env` / Compose; without it the admin API returns 503. The UI prompts for the secret.
- `.env` lives at the repo root and is gitignored. `OPENROUTER_API_KEY` is only needed
  for schema-driven extraction.

## Where the work is going

Internal roadmap docs live under `docs/plan/` (gitignored — local only). Prefer the
BYOK + OSS-first strategy notes over older Phase 4/5 ordering when they conflict.

BYOK: per-user Scrape.do/Scrapfly keys in `provider_credentials` (Fernet). Fetch identity
is a `FetchContext` threaded through strategy/provider/engine. Queue jobs carry
`user_id` only — workers call `build_fetch_context`. Savings: `GET /v1/usage/fetch-savings`
(estimated). See `docs/fetch-savings.md`.

