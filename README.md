# FireScrapling

**AGPL-3.0-only**

Self-hostable cost-control layer for teams already paying [Scrape.do](https://scrape.do) or
[Scrapfly](https://scrapfly.io). Bring your own provider key; escalate fetch tiers only when
needed; turn URLs into LLM-ready Markdown. Flat orchestration — not a credit reseller.

## Why

Always-on anti-bot (ASP / residential) burns credits. FireScrapling runs a cheap-first ladder
and remembers what each domain needed:

| Tier | Modeled weight |
|------|----------------|
| local | 0 |
| sf_static | 1 |
| sf_js | 5 |
| sf_asp | 25 (baseline for “savings”) |
| sf_residential | 75 |

Estimated savings vs always-ASP: `GET /v1/usage/fetch-savings` and the Savings dashboard.
See [docs/fetch-savings.md](docs/fetch-savings.md).

## Quickstart

Requires Docker and curl. No provider API key is needed for the first scrape
(local fetch of `example.com`).

```bash
git clone https://github.com/grayaa/firescrapling.git
cd firescrapling
cp .env.example .env
docker compose up --build -d
```

Wait until the API is healthy:

```bash
# Linux/macOS
until curl -sf http://localhost:8000/health; do sleep 2; done

# Windows PowerShell
# while (-not (curl.exe -sf http://localhost:8000/health)) { Start-Sleep 2 }
```

Create the first account, an API key, and scrape:

```bash
curl -s -X POST http://localhost:8000/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"ops@example.com","password":"ChangeMe99!"}'

TOKEN=$(curl -s -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"ops@example.com","password":"ChangeMe99!"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['session_token'])")

API_KEY=$(curl -s -X POST http://localhost:8000/v1/keys \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"local"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['key']['value'])")

curl -s -X POST http://localhost:8000/v1/scrape \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","formats":["markdown"],"onlyMainContent":true}'
```

If you do not have Python locally, open http://localhost:8080, create the first
account in the UI, create an API key under **API Keys**, then run only the final
`curl` scrape with `fs_…` substituted.

- Dashboard: http://localhost:8080  
- API: http://localhost:8000 (`/docs` for Swagger)

Defaults: `HOSTED_MODE=false`, `PLAYGROUND_ENABLED=false`, `ALLOW_REGISTRATION=false`
(registration closes after the first account; playground is opt-in).

## BYOK

Optional — attach your Scrape.do / Scrapfly key so paid fetches use your meter.

1. Generate an encryption key (needs `cryptography`, or use any Fernet key):
   ```bash
   docker run --rm python:3.11-slim bash -c "pip install -q cryptography && python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
   ```
2. Set in `.env`:
   ```
   BYOK_ENABLED=true
   CREDENTIAL_ENCRYPTION_KEY=<that key>
   ```
3. `docker compose up -d --force-recreate backend worker`
4. Dashboard → **Providers** → add Scrape.do or Scrapfly token (encrypted at rest).

Without BYOK, platform env keys (`SCRAPE_API_KEY` / `SCRAPFLY_API_KEY`) work when
`MANAGED_FETCH_ENABLED=true` (self-host: no plan gating; plan gating only when
`HOSTED_MODE=true`).

## Environment (compose)

| Variable | Default | Notes |
|----------|---------|--------|
| `HOSTED_MODE` | `false` | Billing / plan gates |
| `ALLOW_REGISTRATION` | `false` | Extra signups after first account |
| `PLAYGROUND_ENABLED` | `false` | Unauthenticated demo |
| `BYOK_ENABLED` | `false` | Per-user provider keys |
| `CREDENTIAL_ENCRYPTION_KEY` | — | Required if BYOK on |
| `SCRAPE_API_KEY` / `SCRAPFLY_API_KEY` | — | Platform fetch |
| `FETCH_ESCALATE` | `true` | Cheap-first ladder |
| `LOG_LEVEL` | `INFO` | App / uvicorn logs |
| `SCRAPE_CACHE_TTL` | `3600` | Local HTML cache (seconds) |
| `REDIS_URL` | `redis://redis:6379/0` | RQ workers |
| `ADMIN_SECRET` | — | `/v1/admin/*` |

Full commented list: [`.env.example`](.env.example).

## Architecture

```
browser → frontend :8080 (nginx) → backend :8000 (FastAPI)
                                 → redis + RQ worker
                                 → SQLite (or Postgres profile)
```

Fetch identity is a `FetchContext` (BYOK → platform → local). Queue payloads carry
`user_id` only — never plaintext provider keys.

## MCP

Optional Compose profile:

```bash
docker compose --profile mcp up
```

See [`apps/firescrapling/mcp/README.md`](apps/firescrapling/mcp/README.md) for a Cursor
`.mcp.json` snippet (`FIRESCRAPLING_API_KEY=fs_…`).

## Custom extractors

Site adapters live under `apps/firescrapling/backend/extractors/`. The product surface is
the **registry interface** (`base.py`): return **manifest / media URLs only** — no proxy,
download, cache, or rehost. Shipped anime3rb / reelshort modules are **examples** of that
interface, not the headline feature. See [docs/custom-extractors.md](docs/custom-extractors.md).

## Hosted version?

There is no hosted SaaS tier yet. If you want one, +1 or comment on the
[GitHub Discussions](https://github.com/grayaa/firescrapling/discussions) (see also
[docs/hosted.md](docs/hosted.md)).

## Contributing

- Backend tests: `cd apps/firescrapling/backend && pip install -r requirements-dev.txt && pytest -q`
- Frontend: `cd apps/firescrapling/frontend && npm run typecheck`

## Licence

[AGPL-3.0](LICENSE) — see SPDX identifier `AGPL-3.0-only`.
