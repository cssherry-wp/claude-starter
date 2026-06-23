#!/usr/bin/env bash
# Detect the SDLC stack(s) present in a directory.
# Prints any of: typescript, python, frontend (one per line). Always exits 0.
set -euo pipefail
DIR="${1:-.}"
cd "$DIR" 2>/dev/null || exit 0

emit() { printf '%s\n' "$1"; }

# `find -print -quit` stops at the first match: no full traversal, and no
# SIGPIPE/pipefail false-negative from `| head` closing the pipe early.
has_file() { [ -n "$(find . -maxdepth 2 "$@" -print -quit 2>/dev/null)" ]; }

# TypeScript / Node
if [ -f package.json ] || ls -1 tsconfig*.json >/dev/null 2>&1 \
   || has_file -name '*.ts' -not -path '*/node_modules/*'; then
  emit typescript
fi

# Python
if [ -f pyproject.toml ] || ls -1 requirements*.txt >/dev/null 2>&1 \
   || has_file -name '*.py' -not -path '*/.venv/*'; then
  emit python
fi

# Frontend (React/Vite)
if has_file -name 'vite.config.*' \
   || [ -d frontend ] \
   || { [ -f package.json ] && grep -q '"react"' package.json 2>/dev/null; }; then
  emit frontend
fi
exit 0
