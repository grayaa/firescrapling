"""OpenRouter structured extraction helper."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional


def extract_structured_via_openrouter(
    schema: Dict[str, Any], markdown: Optional[str], html_content: str
) -> Dict[str, Any]:
    """JSON extraction via OpenRouter (OpenAI-compatible API). Requires OPENROUTER_API_KEY."""
    api_key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError(
            "Structured extraction requires OPENROUTER_API_KEY in the environment (e.g. apps/firescrapling/backend/.env)."
        )
    from openai import OpenAI

    default_headers = {}
    referer = (os.environ.get("OPENROUTER_HTTP_REFERER") or "").strip()
    if referer:
        default_headers["HTTP-Referer"] = referer
    title = (os.environ.get("OPENROUTER_APP_TITLE") or "").strip()
    if title:
        default_headers["X-Title"] = title

    client_kwargs: Dict[str, Any] = {
        "base_url": (os.environ.get("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip(),
        "api_key": api_key,
    }
    if default_headers:
        client_kwargs["default_headers"] = default_headers
    client = OpenAI(**client_kwargs)
    model = (os.environ.get("OPENROUTER_MODEL") or "google/gemini-2.0-flash-001").strip()
    body = (markdown or "")[:15000] if markdown else ""
    if not body.strip():
        body = html_content[:15000]
    prompt = (
        "Extract structured data from the following web content according to this JSON schema description. "
        "Respond with a single JSON object only, no markdown fences.\n\n"
        f"Schema (guidance): {json.dumps(schema)}\n\nContent:\n{body}"
    )
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    raw = completion.choices[0].message.content
    if not raw:
        raise RuntimeError("OpenRouter returned empty content")
    return json.loads(raw)


# Alias matching the historical private name in main.py
_extract_structured_via_openrouter = extract_structured_via_openrouter
