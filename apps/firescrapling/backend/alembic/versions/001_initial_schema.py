"""Initial schema (users, keys, jobs, BYOK, fetch_events).

Revision ID: 001_initial
Revises:
Create Date: 2026-08-15

Captures the schema previously created by init_db() + provider_credentials /
fetch_events helpers. Prefer `alembic upgrade head` in deployed environments;
init_db() remains for local/test bootstrap.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("hashed_password", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text()),
        sa.Column("created_at", sa.Text(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key_value", sa.Text(), nullable=False, unique=True),
        sa.Column("key_hash", sa.Text()),
        sa.Column("key_hint", sa.Text()),
        sa.Column("name", sa.Text()),
        sa.Column("last_used", sa.Text()),
        sa.Column("created_at", sa.Text(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_api_keys_key_hash", "api_keys", ["key_hash"], unique=True)

    op.create_table(
        "api_usage",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key_id", sa.Text(), sa.ForeignKey("api_keys.id", ondelete="SET NULL")),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer()),
        sa.Column("response_time_ms", sa.Integer()),
        sa.Column("created_at", sa.Text(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("progress", sa.Integer(), server_default="0"),
        sa.Column("error_message", sa.Text()),
        sa.Column("webhook_url", sa.Text()),
        sa.Column("webhook_secret", sa.Text()),
        sa.Column("created_at", sa.Text(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("finished_at", sa.Text()),
    )

    op.create_table(
        "results",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("job_id", sa.Text(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("markdown", sa.Text()),
        sa.Column("metadata_json", sa.Text()),
        sa.Column("created_at", sa.Text(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.Text(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("progress", sa.Integer()),
        sa.Column("created_at", sa.Text(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.Text(), nullable=False, unique=True),
        sa.Column("expires_at", sa.Text(), nullable=False),
    )

    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("key_id", sa.Text()),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("user_id", "idempotency_key", "endpoint"),
    )

    op.create_table(
        "provider_credentials",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("label", sa.Text()),
        sa.Column("encrypted_key", sa.LargeBinary(), nullable=False),
        sa.Column("key_hint", sa.Text(), nullable=False),
        sa.Column("proxy_pool", sa.Text()),
        sa.Column("residential_pool", sa.Text()),
        sa.Column("country", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default="unverified"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("last_used_at", sa.Text()),
        sa.UniqueConstraint("user_id", "provider"),
    )

    op.create_table(
        "fetch_events",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text()),
        sa.Column("job_id", sa.Text()),
        sa.Column("url", sa.Text()),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text()),
        sa.Column("source", sa.Text()),
        sa.Column("final_tier", sa.Text()),
        sa.Column("attempts_json", sa.Text()),
        sa.Column("profile_hit", sa.Integer(), server_default="0"),
        sa.Column("baseline_cost", sa.Float()),
        sa.Column("actual_cost", sa.Float()),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
    op.create_index("idx_fetch_events_user_created", "fetch_events", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_fetch_events_user_created", table_name="fetch_events")
    op.drop_table("fetch_events")
    op.drop_table("provider_credentials")
    op.drop_table("idempotency_keys")
    op.drop_table("sessions")
    op.drop_table("logs")
    op.drop_table("results")
    op.drop_table("jobs")
    op.drop_table("api_usage")
    op.drop_index("idx_api_keys_key_hash", table_name="api_keys")
    op.drop_table("api_keys")
    op.drop_table("users")
