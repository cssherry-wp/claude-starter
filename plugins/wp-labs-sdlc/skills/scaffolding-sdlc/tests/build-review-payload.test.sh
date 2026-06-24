#!/usr/bin/env bash
# Unit tests for build-review-payload.jq — runs the filter against fixtures and
# compares normalized JSON. Requires: jq. Run: bash tests/build-review-payload.test.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
JQ_FILE="$HERE/../templates/github/workflows/build-review-payload.jq"
MARKER='<!-- claude-autofix -->'
fail=0

run_case() {
  local name="$1" got want
  got="$(jq -f "$JQ_FILE" --arg commit_id "deadbeef" --arg marker "$MARKER" \
        "$HERE/fixtures/$name.input.json" | jq -S .)"
  want="$(jq -S . "$HERE/fixtures/$name.expected.json")"
  if [ "$got" = "$want" ]; then
    echo "PASS: $name"
  else
    echo "FAIL: $name"; diff <(printf '%s\n' "$want") <(printf '%s\n' "$got") || true; fail=1
  fi
}

run_case empty
run_case mixed
run_case multiline
run_case realistic
run_case body_compat
exit "$fail"
