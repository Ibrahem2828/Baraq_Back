#!/bin/sh
set -e

mkdir -p "${MEDIA_ROOT:-/app/media}"

if [ "$DJANGO_RUN_MIGRATIONS" = "1" ]; then
  python manage.py migrate --noinput
fi

if [ "$DJANGO_COLLECTSTATIC" = "1" ]; then
  python manage.py collectstatic --noinput
fi

exec "$@"
