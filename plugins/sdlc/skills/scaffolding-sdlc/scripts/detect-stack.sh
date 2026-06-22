#!/usr/bin/env bash
# Detect the SDLC stack(s) present in a directory.
# Prints any of: typescript, python, frontend (one per line). Always exits 0.
set -euo pipefail
DIR="${1:-.}"
cd "$DIR" 2>/dev/null || exit 0

emit() { printf '%s\n' "$1"; }

# TypeScript / Node
if [ -f package.json ] || ls -1 tsconfig*.json >/dev/null 2>&1 \
   || find . -maxdepth 2 -name '*.ts' -not -path '*/node_modules/*' | head -1 | grep -q .; then
  emit typescript
fi

# Python
if [ -f pyproject.toml ] || ls -1 requirements*.txt >/dev/null 2>&1 \
   || find . -maxdepth 2 -name '*.py' -not -path '*/.venv/*' | head -1 | grep -q .; then
  emit python
fi

# Frontend (React/Vite)
if find . -maxdepth 2 -name 'vite.config.*' | head -1 | grep -q . \
   || [ -d frontend ] \
   || { [ -f package.json ] && grep -q '"react"' package.json 2>/dev/null; }; then
  emit frontend
fi
exit 0
