#!/usr/bin/env bash
# Idempotently ensure the team's managed PR-automation labels exist.
# Requires an authenticated `gh` CLI in a repo with label write access.
set -euo pipefail

ensure() {
  local name="$1" color="$2" desc="$3"
  # --force updates color/description if the label already exists, and creates it otherwise.
  gh label create "$name" --color "$color" --description "$desc" --force
  echo "ensured: $name"
}

ensure "check-in-progress" "fbca04" "Automated checks are running"
ensure "check-pass"        "0e8a16" "Automated checks passed"
ensure "check-fail"        "d73a4a" "Automated checks failed"
ensure "question"          "d876e3" "Needs a human decision (set by comment triage)"
ensure "no-automation"     "ededed" "Opt out of Claude comment-triage auto-fix on this PR"
ensure "dependencies"      "0366d6" "Dependency updates (Dependabot)"
ensure "security"          "b60205" "Security finding or security-related change"
ensure "needs-rebase"      "e99695" "PR is behind main and auto-rebase hit conflicts"
