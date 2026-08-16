"""Document ownership of provider_credentials / fetch_events after removing imperative CREATE.

Revision ID: 002_provider_credentials
Revises: 001_initial
Create Date: 2026-08-15

Tables were already created in 001_initial. This revision records that hot-path
`ensure_*_table()` helpers were removed — schema changes go through Alembic only.
"""
from __future__ import annotations

from typing import Sequence, Union

revision: str = "002_provider_credentials"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No-op: provider_credentials + fetch_events already exist from 001_initial.
    pass


def downgrade() -> None:
    pass
