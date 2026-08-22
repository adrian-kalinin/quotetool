#!/bin/bash
set -e

# Check environment variables
: "${POSTGRES_HOST:?}"
: "${POSTGRES_PORT:?}"

# Define colors and helper functions
MAGENTA='\033[35m'
RED='\033[31m'
NORMAL='\033[0m'

info() { echo -e "${MAGENTA}$1${NORMAL}"; }
error() { echo -e "${RED}$1${NORMAL}" >&2; }

# Wait for the database to be ready (30s timeout)
info "Waiting for database to be ready..."

for i in {1..300}; do
  nc -z "$POSTGRES_HOST" "$POSTGRES_PORT" && break
  sleep 0.1
done

if ! nc -z "$POSTGRES_HOST" "$POSTGRES_PORT"; then
  error "Database not available at ${POSTGRES_HOST}:${POSTGRES_PORT}"
  exit 1
fi

# Run migrations before starting the app
info "Running database migrations..."
python manage.py migrate

# Start the appropriate server
if [ "$DEBUG" != "True" ]; then
    info "Starting Gunicorn server..."
    exec gunicorn --bind 0.0.0.0:8000 config.wsgi:application
else
    info "Starting Django development server..."
    exec python manage.py runserver 0.0.0.0:8000
fi