#!/bin/sh

set -eu

api_pid=""
web_pid=""

cleanup() {
  if [ -n "$web_pid" ]; then
    kill "$web_pid" 2>/dev/null || true
  fi
  if [ -n "$api_pid" ]; then
    kill "$api_pid" 2>/dev/null || true
  fi
  wait "$web_pid" 2>/dev/null || true
  wait "$api_pid" 2>/dev/null || true
}

trap 'cleanup; exit 0' INT TERM

cd /app/backend
migration_attempt=1
migration_max_attempts=12
until alembic upgrade head; do
  if [ "$migration_attempt" -ge "$migration_max_attempts" ]; then
    echo "Database did not become ready for migrations." >&2
    exit 1
  fi
  echo "Database is not ready; retrying migration in 5 seconds." >&2
  migration_attempt=$((migration_attempt + 1))
  sleep 5
done
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
api_pid=$!

cd /app/frontend
node node_modules/next/dist/bin/next start \
  --hostname 0.0.0.0 \
  --port "${PORT:-3000}" &
web_pid=$!

while kill -0 "$api_pid" 2>/dev/null && kill -0 "$web_pid" 2>/dev/null; do
  sleep 2
done

cleanup
exit 1
