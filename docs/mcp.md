# MCP server

Optional Compose profile and package under `apps/firescrapling/mcp/`.

```bash
docker compose --profile mcp up
```

Auth: `FIRESCRAPLING_API_KEY=fs_…` and `FIRESCRAPLING_BASE_URL=http://backend:8000`.

Cursor / Claude: see `apps/firescrapling/mcp/README.md` for a `.mcp.json` snippet.

Tools wrap the HTTP API (scrape, crawl, status, map, extract_media, fetch_savings).
