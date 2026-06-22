#!/usr/bin/env bash
# Creates docs/YYYY-MM-DD-HHmm_<goal>.md after each git commit and amends the
# commit to include it.
#
# Wired as a Stop hook (see ~/.claude/settings.json), so it inspects the latest
# commit rather than a tool command. The Stop payload provides .session_id but
# NOT .tool_input.command, so the recency + non-doc-file checks below are what
# gate execution.
set -euo pipefail

INPUT=$(cat)
SESSION_ID=$(printf '%s' "$INPUT" | jq -r '.session_id // ""')

# Must be in a git repo
git rev-parse --git-dir > /dev/null 2>&1 || exit 0

# Ensure the commit is recent (within 60s) so we don't act on a pre-existing commit
COMMIT_TIME=$(git log -1 --format='%ct' 2>/dev/null) || exit 0
[ -z "$COMMIT_TIME" ] && exit 0
[ $(( $(date +%s) - COMMIT_TIME )) -gt 60 ] && exit 0

# Skip if the commit only touches docs/ (prevents acting on doc-only commits)
NON_DOC=$(git show --name-only --format='' HEAD 2>/dev/null | grep -v '^docs/' | head -1)
[ -z "$NON_DOC" ] && exit 0

# Skip if this commit already includes a generated doc, so re-firing the Stop
# hook within the 60s window doesn't re-amend the same commit repeatedly.
git show --name-only --format='' HEAD 2>/dev/null \
  | grep -qE '^docs/[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{4}_.*\.md$' && exit 0

SUBJECT=$(git log -1 --format='%s')
BODY=$(git log -1 --format='%b')
HASH=$(git log -1 --format='%h')
DATE=$(date +%Y-%m-%d-%H%M)
SLUG=$(printf '%s' "$SUBJECT" \
  | tr '[:upper:]' '[:lower:]' \
  | tr -cs 'a-z0-9' '_' \
  | sed 's/^_//;s/_$//')

GIT_DIR=$(git rev-parse --git-dir)
if [ -n "$SESSION_ID" ] && [ -f "${GIT_DIR}/CLAUDE_SESSION_${SESSION_ID}" ]; then
  SESSION_SUMMARY=$(cat "${GIT_DIR}/CLAUDE_SESSION_${SESSION_ID}")
  rm -f "${GIT_DIR}/CLAUDE_SESSION_${SESSION_ID}"
elif [ -f "${GIT_DIR}/CLAUDE_SESSION_SUMMARY" ]; then
  SESSION_SUMMARY=$(cat "${GIT_DIR}/CLAUDE_SESSION_SUMMARY")
  rm -f "${GIT_DIR}/CLAUDE_SESSION_SUMMARY"
else
  SESSION_SUMMARY=""
fi

mkdir -p docs
DOC="docs/${DATE}_${SLUG}.md"

{
  printf '# %s\n\n' "$SUBJECT"
  # The backticks below are literal Markdown (they render the hash as inline
  # code), NOT shell command substitution. The values are substituted by
  # printf from the double-quoted args, so single quotes here are correct.
  # shellcheck disable=SC2016
  printf '**Date**: %s  \n**Commit**: `%s`\n\n' "$DATE" "$HASH"
  [ -n "$BODY" ] && printf '%s\n' "$BODY"
  if [ -n "$SESSION_SUMMARY" ]; then
    printf '\n## Session Summary\n\n%s\n' "$SESSION_SUMMARY"
  fi
} > "$DOC"

git add "$DOC" && git commit --amend --no-edit
