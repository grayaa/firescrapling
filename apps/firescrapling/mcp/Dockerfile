FROM python:3.11-slim-bookworm

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV FIRESCRAPLING_BASE_URL=http://backend:8000

# Stdio MCP — attach with: docker compose run -i mcp
CMD ["python", "server.py"]
