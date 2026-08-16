# FireScrapling MCP server

Thin MCP tools over the FireScrapling HTTP API. Auth with an `fs_…` API key.

## Env

| Variable | Default | Required |
|----------|---------|----------|
| `FIRESCRAPLING_API_KEY` | — | yes (`fs_…`) |
| `FIRESCRAPLING_BASE_URL` | `http://localhost:8000` | no |

## Tools

- `scrape` — scrape URL → markdown
- `crawl` — start crawl job
- `crawl_status` — poll crawl + paginated results
- `map` — discover links
- `extract_media` — media/catalog manifests (URLs only)
- `fetch_savings` — estimated credit savings

## Local run

```bash
cd apps/firescrapling/mcp
pip install -r requirements.txt
export FIRESCRAPLING_API_KEY=fs_…
export FIRESCRAPLING_BASE_URL=http://localhost:8000
python server.py
```

## Cursor / Claude Code — `.mcp.json`

Place in the project root (or user MCP config):

```json
{
  "mcpServers": {
    "firescrapling": {
      "command": "python",
      "args": ["apps/firescrapling/mcp/server.py"],
      "env": {
        "FIRESCRAPLING_API_KEY": "fs_YOUR_KEY",
        "FIRESCRAPLING_BASE_URL": "http://localhost:8000"
      }
    }
  }
}
```

On Windows, prefer an absolute path for `args[0]` if the workspace root differs.

## Docker Compose

Optional service (see repo `docker-compose.yml`):

```bash
docker compose --profile mcp up mcp
```

The MCP container speaks stdio; Compose keeps the image buildable for agents that
attach via `docker compose run -i mcp`.
