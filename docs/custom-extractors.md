# Custom extractors

FireScrapling can run **site-specific extractors** that return structured media / link
metadata from HTML (or a light network capture when required).

## Boundary (read this first)

- Extractors return **manifest URLs and metadata only**.
- FireScrapling does **not** proxy, download, cache, or rehost media.
- Crawl and fetch paths still honour **robots.txt** and politeness delays.

If you need bytes on disk, use your own tooling against the URLs you are allowed to fetch.

## Framework

1. Implement the protocol in [`extractors/base.py`](../apps/firescrapling/backend/extractors/base.py).
2. Register the extractor in the package registry (`extractors/__init__.py`).
3. Call `POST /v1/extract/media` with a URL; list support via
   `GET /v1/extract/media/supported`.

## Examples

The repo ships small adapters (e.g. anime3rb, reelshort) as **examples of the
interface**, not as product headlines. Prefer writing your own extractor for sites you
operate or are licensed to process.
