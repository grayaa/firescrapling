"""Export OpenAPI schema from the FastAPI app to openapi.yaml.

Usage (from apps/firescrapling/backend):
  python scripts/export_openapi.py
  python scripts/export_openapi.py --check   # exit 1 if openapi.yaml drifted
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

# Avoid BYOK fail-closed during schema export in CI without secrets.
os.environ.setdefault("BYOK_ENABLED", "false")
os.environ.setdefault("QUEUE_ENABLED", "false")
os.environ.setdefault("FETCH_PROVIDER", "local")


def _to_yaml(data: object) -> str:
    try:
        import yaml  # type: ignore
    except ImportError:
        # Fallback: JSON is valid enough for CI diff when PyYAML missing.
        return json.dumps(data, indent=2, sort_keys=True) + "\n"
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=os.path.join(_BACKEND, "openapi.yaml"),
        help="Output path (default: openapi.yaml next to api_server.py)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare generated schema to existing file; non-zero if different",
    )
    args = parser.parse_args()

    from api_server import app

    schema = app.openapi()
    rendered = _to_yaml(schema)

    if args.check:
        if not os.path.isfile(args.out):
            print(f"missing {args.out}", file=sys.stderr)
            return 1
        with open(args.out, encoding="utf-8") as f:
            existing = f.read()
        if existing.strip() != rendered.strip():
            print(f"openapi.yaml out of date — run: python scripts/export_openapi.py", file=sys.stderr)
            return 1
        print("openapi.yaml is up to date")
        return 0

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(rendered)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
