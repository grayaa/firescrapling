#!/usr/bin/env python3
"""Re-encrypt all provider_credentials onto the primary Fernet key.

Usage (from apps/firescrapling/backend):

  # Newest key first, then previous keys that can still decrypt rows:
  export CREDENTIAL_ENCRYPTION_KEYS="$NEW_KEY,$OLD_KEY"
  python scripts/rotate_credential_keys.py

After success, drop old keys from CREDENTIAL_ENCRYPTION_KEYS / set
CREDENTIAL_ENCRYPTION_KEY=$NEW_KEY only.
"""
from __future__ import annotations

import os
import sys

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


def main() -> int:
    from db import init_db
    from provider_credentials import reencrypt_all_credentials
    from settings import clear_settings_cache, get_settings

    clear_settings_cache()
    settings = get_settings()
    if not settings.credential_encryption_keys:
        print("ERROR: set CREDENTIAL_ENCRYPTION_KEY or CREDENTIAL_ENCRYPTION_KEYS", file=sys.stderr)
        return 1
    init_db()
    n = reencrypt_all_credentials()
    print(f"Re-encrypted {n} credential(s) onto primary key.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
