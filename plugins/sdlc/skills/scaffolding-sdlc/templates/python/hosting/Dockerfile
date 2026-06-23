# Python (Django + DRF) API container.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/usr/local \
    PORT=8000

WORKDIR /app

# uv binary for dependency install (matches the project's uv-based tooling).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install runtime deps + prod extras (gunicorn, psycopg) into system python.
# --no-install-project installs only dependencies (the app isn't a wheel).
COPY pyproject.toml ./
RUN uv sync --extra prod --no-dev --no-install-project

COPY . .

# Collect static files (served by WhiteNoise). A throwaway key avoids needing
# the real secret at build time.
RUN DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput

EXPOSE 8000

# Migrate then serve. DATABASE_URL selects Postgres; otherwise SQLite.
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT}"]
