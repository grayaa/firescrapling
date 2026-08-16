# Connect your provider

## Platform keys (env)

Set one of:

- `SCRAPE_API_KEY` (Scrape.do) — preferred in `FETCH_PROVIDER=auto`
- `SCRAPFLY_API_KEY` (Scrapfly)

`FETCH_ESCALATE=true` (default) probes cheap tiers first.

## BYOK (dashboard)

1. `BYOK_ENABLED=true`
2. `CREDENTIAL_ENCRYPTION_KEY=<fernet>`
3. Dashboard → Providers → add key → Verify

Resolution order: **user BYOK → platform env (if managed fetch allowed) → local**.
