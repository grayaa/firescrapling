FROM python:3.11-slim-bookworm AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

COPY . .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Dev / CI image — build with: docker build --target test …
FROM base AS test
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
CMD ["pytest", "-q"]

# Default image (must be last stage so `docker compose build` runs the API).
FROM base AS runtime
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
