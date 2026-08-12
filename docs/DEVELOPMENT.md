# Development guide

Everything you need to pick this project up cold. Start with [`AGENTS.md`](../AGENTS.md)
for the architecture map and the invariants; this file covers setup, workflow and
verification.

## Setup

```bash
git clone https://github.com/grayaa/firescrapling.git
cd firescrapling
cp .env.example .env      # OPENROUTER_API_KEY only needed for schema extraction
```

### Option A — Docker (closest to production)

```bash
docker compose up --build
```

Dashboard on http://localhost:8080, API on http://localhost:8000 (`/docs` for Swagger).
nginx proxies `/v1` and `/health` from the frontend container to the backend, so the SPA
runs same-origin. Backend data lives in the `backend-data` volume.

### Option B — Local processes (faster iteration)

```bash
# Terminal 1 — backend
cd apps/firescrapling/backend
python -m venv .venv && . .venv/Scripts/activate   # Windows; use bin/activate elsewhere
pip install -r requirements.txt
playwright install chromium                        # only needed for actions/screenshots
uvicorn api_server:app --reload --port 8000

# Terminal 2 — frontend
cd apps/firescrapling/frontend
npm install
npm run dev            # :5173, vite proxies /v1 and /health to :8000
```

Set `API_ALLOW_PRIVATE_URLS=true` in `.env` if you want to scrape localhost fixtures
during development. Leave it off otherwise — it is the SSRF guard.

## Working on it

| Task | Command |
|---|---|
| Type check (catches render crashes) | `cd apps/firescrapling/frontend && npm run typecheck` |
| Production build | `npm run build` |
| Engine checks (local fixture server, no network) | `python apps/firescrapling/backend/scripts/run_scraping_tests.py` |
| Full-stack smoke | `docker compose up --build` then the loop below |

### The smoke loop

The one path worth re-running after any change to auth, jobs or the dashboard:

```bash
# 1. account
curl -sX POST localhost:8000/v1/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"dev@example.com","password":"devpassword","full_name":"Dev"}'
TOKEN=$(curl -sX POST localhost:8000/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"dev@example.com","password":"devpassword"}' \
  | sed -n 's/.*"session_token":"\([^"]*\)".*/\1/p')

# 2. key
KEY=$(curl -sX POST localhost:8000/v1/keys -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"name":"dev"}' \
  | sed -n 's/.*"value":"\([^"]*\)".*/\1/p')

# 3. work
curl -sX POST localhost:8000/v1/scrape -H "Authorization: Bearer $KEY" \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com","formats":["markdown"]}'

# 4. the dashboard's data source should now reflect it
curl -s "localhost:8000/v1/usage/summary?days=30" -H "Authorization: Bearer $TOKEN"
```

In the browser: register → Overview loads with no console error → API Keys → create →
Playground → paste the key → scrape → Overview counters move.

## Conventions

Covered in [`AGENTS.md`](../AGENTS.md) and enforced in prose by `.cursor/rules/*.mdc`
(Cursor loads these automatically; `project.mdc` always, the others by file path). The
short version:

- Routes thin in `api_server.py`, logic in `main.py`, fetching in `scraping_engine.py`.
- All frontend API calls go through `src/restClient.ts`, with an explicit `auth` mode.
- Session tokens and API keys are different credentials for different route groups.
- Every user-supplied URL goes through `validate_request_url`.
- Commit an open SQLite transaction before calling a helper that opens its own
  connection.

## Debugging

- **`database is locked`** — a write happened through a second connection while a
  transaction was open. Find the helper call and commit before it.
- **Blank screen after login** — almost always a missing import surfacing as
  `ReferenceError`. `npm run typecheck`.
- **401 on `/v1/keys`** — a session token is required there, not an API key.
- **400 `invalid_url`** — the SSRF guard. Private/loopback targets need
  `API_ALLOW_PRIVATE_URLS=true`.
- **429** — the in-process sliding window (`RATE_LIMIT_PER_MINUTE`, and a tighter
  per-IP limit for playground routes).
- Backend logs: `docker compose logs -f backend`. Every response carries
  `X-Request-ID`, which appears in the error body too.

## What to build next

`docs/plan/00-current-plan.md` is the active, triaged roadmap. Phase 1 (make the
dashboard real) is done; Phase 2 (tests + CI) is the next unstarted work.
