# Self-host quickstart

1. `cp .env.example .env` — only `CORS_ORIGINS` is required; the rest is optional.
2. Optional: set `SCRAPE_API_KEY` or `SCRAPFLY_API_KEY` for paid fetch.
3. Optional BYOK: set `BYOK_ENABLED=true` and `CREDENTIAL_ENCRYPTION_KEY` (see README).
4. `docker compose up --build`
5. Open http://localhost:8080 → **Register** (login page) → create an API key → scrape.

Sign-up after the first account is off by default (`ALLOW_REGISTRATION=false`). The first
account is always allowed; set `ALLOW_REGISTRATION=true` to keep registration open.

## Defaults (no need to set these)

| Variable | Default | Notes |
|----------|---------|--------|
| `HOSTED_MODE` | `false` | Self-host; billing off |
| `PLAYGROUND_ENABLED` | `false` | Opt-in unauthenticated demo |
| `ALLOW_REGISTRATION` | `false` | First account always; then closed |
| `FETCH_ESCALATE` | `true` | Cheap-first ladder |
| `REDIS_URL` | `redis://redis:6379/0` | Compose Redis |
| `QUEUE_ENABLED` | `true` | RQ workers |
| `LOG_LEVEL` | `INFO` | |
| `SCRAPE_CACHE_TTL` | `3600` | Local HTML cache (seconds) |
| `MANAGED_FETCH_ENABLED` | `true` | Use env provider keys when set |
| `DATABASE_URL` | _(empty)_ | SQLite by default; set for Postgres |

## Optional Postgres

Default storage is **SQLite** (Settings → Database shows `sqlite`). To use Postgres:

```bash
# .env
DATABASE_URL=postgresql+psycopg://firescrapling:firescrapling@postgres:5432/firescrapling
```

```bash
docker compose --profile postgres up --build
```

That starts the `postgres` service and points the API/worker at it. The container
listens on `postgres:5432` inside the Compose network; on the host it is mapped to
`localhost:5433` by default (`POSTGRES_HOST_PORT`) to avoid clashing with another
local Postgres on `5432`. Migrations run automatically on startup
(`alembic upgrade head`). Override `POSTGRES_USER` / `POSTGRES_PASSWORD` /
`POSTGRES_DB` if you change the URL credentials.

After startup, Settings → Database should show `postgres`. For pytest against
Postgres, point `TEST_DATABASE_URL` at a dedicated database (e.g. `firescrapling_test`).

Other advanced knobs (Stripe, playground limits, crawl concurrency, OpenRouter) live in
`docker-compose.yml` as `${VAR:-default}` — set them in `.env` only if you need to override.

Next: [Connect your provider](./connect-provider.md) · [Fetch ladder](./fetch-ladder.md) ·
[Savings](./fetch-savings.md)
