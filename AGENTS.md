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
docker-compose.yml            backend :8000, nginx-served frontend :8080
```

### Backend files, by responsibility

| File | Owns |
|---|---|
| `api_server.py` | All HTTP routes, request/response models, error envelope, CORS, request ids |
| `api_auth.py` | FastAPI dependencies: API-key auth, session auth, rate limiting |
| `main.py` | Business logic: accounts, keys, jobs, usage aggregation, job orchestration |
| `scraping_engine.py` | Fetching, retries, markdown extraction, BFS crawl, robots, cache |
| `security_url.py` | SSRF guard — validates every user-supplied target URL |
| `webhook_delivery.py` | HMAC-signed webhook POSTs with retry/backoff |

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
- **Jobs run in daemon threads** (`spawn_scrape_thread` / `spawn_crawl_thread`). They do
  not survive a restart, and there is no concurrency cap. Treat this as temporary.
- The admin console (`features/admin-dashboard.tsx`) is still demo data, hidden unless
  the frontend is built with `VITE_ADMIN_DEMO=true`. Don't cite its numbers as real.
- `.env` lives at the repo root and is gitignored. `OPENROUTER_API_KEY` is only needed
  for schema-driven extraction.

## Where the work is going

`docs/plan/` holds the phased roadmap; `docs/plan/00-current-plan.md` is the active one
(tests + CI, then Postgres/Redis/worker queue, then billing, then engine features).
Read it before proposing architecture changes — the known gaps are already triaged.
