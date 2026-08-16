#!/bin/sh
set -e
# Non-sqlite URLs need schema from Alembic (init_db skips CREATE for Postgres).
case "${DATABASE_URL:-}" in
  postgresql*|postgres*)
    echo "DATABASE_URL is Postgres — running alembic upgrade head"
    alembic upgrade head
    ;;
esac
exec "$@"
