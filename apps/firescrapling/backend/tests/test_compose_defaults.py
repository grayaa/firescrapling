"""Guard docker-compose.yml secure defaults — app tests alone miss deploy config."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

# Compose file lives at the repo root; when pytest runs in Docker the backend is
# bind-mounted at /app, so walk upward instead of assuming a fixed depth.
def _find_compose() -> Path:
    roots = [Path(__file__).resolve().parent, Path.cwd(), Path("/repo")]
    seen: set[Path] = set()
    for root in roots:
        for parent in [root, *root.parents]:
            if parent in seen:
                continue
            seen.add(parent)
            candidate = parent / "docker-compose.yml"
            if candidate.is_file():
                return candidate
    raise FileNotFoundError(
        "docker-compose.yml not found — run pytest from a full checkout "
        "(or mount the repo at /repo)"
    )


# Compose interpolations we require on the backend service.
_EXPECTED_DEFAULTS = {
    "ALLOW_REGISTRATION": "false",
    "PLAYGROUND_ENABLED": "false",
    "HOSTED_MODE": "false",
    "BYOK_ENABLED": "false",
    "API_REQUIRE_AUTH": "true",
}


def _interpolation_default(raw: str, key: str) -> str:
    """Extract the default from ``${KEY:-default}`` (Compose interpolation)."""
    text = str(raw).strip()
    m = re.fullmatch(rf"\$\{{{re.escape(key)}:-([^}}]*)\}}", text)
    assert m is not None, (
        f"backend environment.{key} must use ${{{key}:-…}} form, got {raw!r}"
    )
    return m.group(1)


def test_compose_backend_secure_defaults() -> None:
    compose_path = _find_compose()
    doc = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    env = doc["services"]["backend"]["environment"]
    for key, expected in _EXPECTED_DEFAULTS.items():
        assert key in env, f"backend environment missing {key}"
        got = _interpolation_default(env[key], key)
        assert got == expected, f"{key} compose default is {got!r}, expected {expected!r}"
