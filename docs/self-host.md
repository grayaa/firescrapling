# Self-host quickstart

1. `cp .env.example .env` — only `CORS_ORIGINS` is required; the rest is optional.
2. Optional: set `SCRAPE_API_KEY` or `SCRAPFLY_API_KEY` for paid fetch.
3. Optional BYOK: set `BYOK_ENABLED=true` and `CREDENTIAL_ENCRYPTION_KEY` (see README).
4. `docker compose up --build`
5. Open http://localhost:8080 → **Register** (login page) → create an API key → scrape.

Sign-up is enabled by default (`ALLOW_REGISTRATION=true`). Set it to `false` to allow only
the first account.

## Defaults (no need to set these)

| Variable | Default | Notes |
|----------|---------|--------|
| `HOSTED_MODE` | `false` | Self-host; billing off |
| `PLAYGROUND_ENABLED` | `false` | Opt-in unauthenticated demo |
| `ALLOW_REGISTRATION` | `true` | Login-page registration |
| `FETCH_ESCALATE` | `true` | Cheap-first ladder |
| `REDIS_URL` | `redis://redis:6379/0` | Compose Redis |
| `QUEUE_ENABLED` | `true` | RQ workers |
| `LOG_LEVEL` | `INFO` | |
| `SCRAPE_CACHE_TTL` | `3600` | Local HTML cache (seconds) |
| `MANAGED_FETCH_ENABLED` | `true` | Use env provider keys when set |

Advanced knobs (`DATABASE_URL`, Stripe, playground limits, crawl concurrency, OpenRouter)
live in `docker-compose.yml` as `${VAR:-default}` — set them in `.env` only if you need
to override.

Next: [Connect your provider](./connect-provider.md) · [Fetch ladder](./fetch-ladder.md) ·
[Savings](./fetch-savings.md)
