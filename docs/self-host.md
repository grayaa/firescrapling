# Self-host quickstart

1. `cp .env.example .env`
2. Optional: set `SCRAPE_API_KEY` or `SCRAPFLY_API_KEY` for paid fetch.
3. Optional BYOK: set `BYOK_ENABLED=true` and `CREDENTIAL_ENCRYPTION_KEY` (see README).
4. `docker compose up --build`
5. Open http://localhost:8080 → create the **first** account → API key → scrape.

Registration closes after the first user unless `ALLOW_REGISTRATION=true`.

Keep `HOSTED_MODE=false` unless you intentionally run the commercial surface.
Keep `PLAYGROUND_ENABLED=false` unless you want an unauthenticated demo that can burn
provider credits.

Next: [Connect your provider](./connect-provider.md) · [Fetch ladder](./fetch-ladder.md) ·
[Savings](./fetch-savings.md)
