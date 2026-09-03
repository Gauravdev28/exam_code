#!/bin/sh
set -e

echo "Running CODEGUARD backend entrypoint..."

# If MySQL host is defined and not using sqlite, wait for DB
if [ "$DB_HOST" != "" ] && [ "$USE_SQLITE_DEV" != "True" ]; then
  echo "Waiting for database at $DB_HOST:${DB_PORT:-3306}..."
  while ! nc -z "$DB_HOST" "${DB_PORT:-3306}"; do
    sleep 1
  done
  echo "Database is ready."
fi

# Execute database migrations
python manage.py migrate --noinput

exec "$@"
