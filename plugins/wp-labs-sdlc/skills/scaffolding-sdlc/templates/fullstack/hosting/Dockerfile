# Fullstack container: build the React SPA, then serve it + the Django API.

# --- Stage 1: build the frontend ---
FROM node:20-slim AS frontend
WORKDIR /src/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build   # outputs frontend/dist

# --- Stage 2: Python runtime ---
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/usr/local \
    PORT=8000

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml ./
RUN uv sync --extra prod --no-dev --no-install-project

COPY . .
# Bring the built SPA in so Django/WhiteNoise can serve it.
COPY --from=frontend /src/frontend/dist ./frontend/dist

RUN DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput

EXPOSE 8000

# RUN_MIGRATIONS_ON_START (default true) lets the entrypoint migrate — safe on a
# single instance (App Service). On Azure Container Apps it is set to "false" so a
# dedicated migration Job owns migrations (multiple replicas would otherwise race).
# CREATE_SUPERUSER_ON_START (default false) seeds an admin from DJANGO_SUPERUSER_*
# env vars — used by ephemeral SQLite preview environments (idempotent: || true).
CMD ["sh", "-c", "if [ \"${RUN_MIGRATIONS_ON_START:-true}\" = \"true\" ]; then python manage.py migrate --noinput; fi && if [ \"${CREATE_SUPERUSER_ON_START:-false}\" = \"true\" ]; then python manage.py createsuperuser --noinput || true; fi && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT}"]
