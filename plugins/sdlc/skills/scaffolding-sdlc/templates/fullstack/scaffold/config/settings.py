"""Minimal Django settings for the starter API.

Secure-by-default: DEBUG is off unless explicitly enabled, hosts are
loopback-only unless configured, and the secret key comes from the
environment (a random per-process key is used only as a dev fallback so the
app still runs locally without committing a predictable secret).

Database: SQLite for local dev/tests; set DATABASE_URL (e.g. a Postgres URL
from Docker/Azure) to switch to Postgres without code changes.
"""

import os
import secrets
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get("DJANGO_DEBUG", "") == "1"

# Prefer an explicit env secret; fall back to a random per-process key for dev.
# Never a hardcoded/predictable value, so nothing sensitive is committed.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or secrets.token_urlsafe(50)

_hosts = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
ALLOWED_HOSTS = [h for h in _hosts.split(",") if h]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    "rest_framework",
    "api",
]

MIDDLEWARE = [
    # WhiteNoise serves collected static files in the container.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"

# Postgres when DATABASE_URL is set (Docker/Azure); SQLite for local dev/tests.
_db_url = os.environ.get("DATABASE_URL")
if _db_url:
    _u = urlparse(_db_url)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _u.path.lstrip("/"),
            "USER": _u.username or "",
            "PASSWORD": _u.password or "",
            "HOST": _u.hostname or "",
            "PORT": str(_u.port or 5432),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Built React SPA (frontend/dist). Present in the container after the Vite
# build stage; absent during local dev/tests (frontend runs on its own server).
_FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
STATICFILES_DIRS = [_FRONTEND_DIST] if _FRONTEND_DIST.exists() else []

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [_FRONTEND_DIST] if _FRONTEND_DIST.exists() else [],
        "APP_DIRS": True,
        "OPTIONS": {},
    }
]

# Secure default: endpoints require auth unless a view opts out explicitly.
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
}
