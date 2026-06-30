#!/usr/bin/env bash
# Refresh the vendored wp-labs-superpowers fork from the superpowers snapshot that
# anthropics/claude-plugins-official currently pins (a specific, vetted
# obra/superpowers commit) — i.e. track Anthropic's curated release, not
# upstream HEAD.
#
# Detects a new upstream release by comparing the upstream plugin.json `version`
# against our fork's base version (the part before the `-team.N` suffix). If they
# differ, it rebuilds plugins/wp-labs-superpowers from upstream and re-applies the
# team docs-path convention. It does NOT commit — the CI workflow (or you) commits
# and opens the PR.
#
# Usage:
#   scripts/refresh-superpowers-fork.sh           # rebuild fork if upstream is newer
#   scripts/refresh-superpowers-fork.sh --check   # report only, make no changes
#
# Outputs (also written to $GITHUB_OUTPUT when set): changed, version, sha
set -euo pipefail

MARKETPLACE_REPO="https://github.com/anthropics/claude-plugins-official.git"
ROOT=$(cd "$(dirname "$0")/.." && pwd)
FORK_DIR="$ROOT/plugins/wp-labs-superpowers"
MODE="${1:-refresh}"

emit() { [ -n "${GITHUB_OUTPUT:-}" ] && echo "$1" >>"$GITHUB_OUTPUT" || true; }
ver() { node -e 'console.log(require(process.argv[1]).version)' "$1"; }

current_version=$(ver "$FORK_DIR/.claude-plugin/plugin.json")
current_base="${current_version%%-team*}"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# Resolve the superpowers source the official marketplace currently blesses: its
# manifest pins obra/superpowers to a specific, vetted commit. Building from that
# commit tracks Anthropic's curated snapshot rather than upstream HEAD.
git clone --quiet --depth 1 "$MARKETPLACE_REPO" "$TMP/mp"
read -r src_url src_sha <<<"$(node -e '
  const m = require(process.argv[1]);
  const p = (m.plugins || []).find((x) => x.name === "superpowers");
  if (!p || !p.source || !p.source.url) {
    console.error("superpowers source not found in official marketplace manifest");
    process.exit(1);
  }
  process.stdout.write(p.source.url + " " + (p.source.sha || ""));
' "$TMP/mp/.claude-plugin/marketplace.json")"

# Fetch just the pinned commit (falls back to default HEAD if the manifest pins
# by branch rather than sha).
src="$TMP/up"
mkdir -p "$src"
git -C "$src" init -q
git -C "$src" fetch --quiet --depth 1 "$src_url" "${src_sha:-HEAD}"
git -C "$src" checkout --quiet FETCH_HEAD
upstream_version=$(ver "$src/.claude-plugin/plugin.json")
upstream_sha=$(git -C "$src" rev-parse HEAD)

if [ "$upstream_version" = "$current_base" ]; then
  echo "Up to date: fork base $current_base == upstream $upstream_version"
  emit "changed=false"
  exit 0
fi

echo "New upstream version detected: $upstream_version (current fork base: $current_base)"
emit "changed=true"
emit "version=$upstream_version"
emit "sha=$upstream_sha"

if [ "$MODE" = "--check" ]; then
  exit 0
fi

# --- Rebuild the fork from upstream, keeping only plugin essentials -----------
rm -rf "$FORK_DIR/skills" "$FORK_DIR/hooks" "$FORK_DIR/LICENSE" "$FORK_DIR/README.md"
cp -R "$src/skills" "$FORK_DIR/skills"
[ -d "$src/hooks" ] && cp -R "$src/hooks" "$FORK_DIR/hooks"
[ -f "$src/LICENSE" ] && cp "$src/LICENSE" "$FORK_DIR/LICENSE"
[ -f "$src/README.md" ] && cp "$src/README.md" "$FORK_DIR/README.md"
# Drop other-harness hook variants and any cruft; never vendor a nested marketplace.json
rm -f "$FORK_DIR/hooks/hooks-codex.json" "$FORK_DIR/hooks/hooks-cursor.json"
rm -rf "$FORK_DIR/hooks/session-start-codex"
rm -f "$FORK_DIR/.claude-plugin/marketplace.json"
find "$FORK_DIR" -name '.DS_Store' -delete

# --- Apply the team docs-path convention to the skill text --------------------
while IFS= read -r f; do
  sed -i.bak -e 's#docs/superpowers/specs#.superpowers/01-specs#g' \
             -e 's#docs/superpowers/plans#.superpowers/02-plans#g' "$f"
  rm -f "$f.bak"
done < <(grep -rl 'docs/superpowers/\(specs\|plans\)' "$FORK_DIR/skills" 2>/dev/null || true)

# Best-effort HHmm filename patterns (skip silently if upstream changed the wording).
# NOTE: the loop above has already rewritten the docs/superpowers/{specs,plans}
# prefix to .superpowers/{01-specs,02-plans}, so these patterns must match the
# already-rewritten prefix — not the original upstream one.
sed -i.bak 's#.superpowers/01-specs/YYYY-MM-DD-<topic>-design\.md#.superpowers/01-specs/YYYY-MM-DD-HHmm-<name-of-spec>.md#g' \
  "$FORK_DIR/skills/brainstorming/SKILL.md" 2>/dev/null && rm -f "$FORK_DIR/skills/brainstorming/SKILL.md.bak" || true
sed -i.bak 's#.superpowers/02-plans/YYYY-MM-DD-<feature-name>\.md#.superpowers/02-plans/YYYY-MM-DD-HHmm-<name-of-plan>.md#g' \
  "$FORK_DIR/skills/writing-plans/SKILL.md" 2>/dev/null && rm -f "$FORK_DIR/skills/writing-plans/SKILL.md.bak" || true

# --- Re-apply team workflow overlays (survive the upstream rebuild) ----------
OVERLAY_DIR="$FORK_DIR/team-overlays"
if [ -d "$OVERLAY_DIR" ]; then
  for frag in "$OVERLAY_DIR"/*.md; do
    [ -e "$frag" ] || continue
    skill_name=$(basename "$frag" .md)
    target="$FORK_DIR/skills/$skill_name/SKILL.md"
    [ -f "$target" ] || continue
    if ! grep -q 'wp-labs team overlay: BEGIN' "$target"; then
      printf '\n' >>"$target"
      cat "$frag" >>"$target"
    fi
  done
fi

# --- Rewrite our plugin manifest and FORK.md ---------------------------------
new_version="${upstream_version}-team.1"
node - "$FORK_DIR/.claude-plugin/plugin.json" "$new_version" <<'NODE'
const fs = require("fs");
const [, , file, version] = process.argv;
const manifest = {
  name: "wp-labs-superpowers",
  description:
    "Team fork of superpowers (TDD, debugging, brainstorming, plans) with the team docs-path convention baked in. Enable instead of stock superpowers — never both.",
  version,
  author: { name: "Sherry Zhou", email: "szhou@wp-labs.ai" },
  homepage: "https://github.com/cssherry-wp/wp-labs-starter",
  repository: "https://github.com/cssherry-wp/wp-labs-starter",
  license: "MIT",
  keywords: ["skills", "tdd", "debugging", "collaboration", "best-practices", "workflows", "fork"],
};
fs.writeFileSync(file, JSON.stringify(manifest, null, 2) + "\n");
NODE

cat >"$FORK_DIR/FORK.md" <<EOF
# wp-labs-superpowers — fork notes

This is a vendored fork of [superpowers](https://github.com/obra/superpowers), trimmed to the
plugin essentials and customized with the team docs-path convention.

## Upstream base

- Source: \`obra/superpowers\` (the commit pinned by \`anthropics/claude-plugins-official\`)
- Version: **${upstream_version}**
- Base commit: **\`${upstream_sha}\`**
- License: MIT (see \`LICENSE\`)

## What diverges from upstream

1. **Docs-path convention** applied to the skill text:
   - \`docs/superpowers/specs/...\` → \`.superpowers/01-specs/YYYY-MM-DD-HHmm-<name-of-spec>.md\`
   - \`docs/superpowers/plans/...\` → \`.superpowers/02-plans/YYYY-MM-DD-HHmm-<name-of-plan>.md\`
2. **Slimmed to plugin essentials** — kept \`.claude-plugin/\`, \`skills/\`, \`hooks/\`, \`LICENSE\`,
   \`README.md\`; removed upstream dev/CI/test files, the upstream project's own \`docs/\`, and
   other-harness directories.
3. **Team workflow overlays** — spec→issue (brainstorming), plan→comment (writing-plans), and
   feature-docs (finishing-a-development-branch) are appended from \`team-overlays/\` after each
   rebuild.

## Why a fork (vs the overlay)

The default delivery is the lightweight \`team-docs-convention\` skill in the \`standards\` plugin.
This fork bakes the paths into the skill text. Enable **either** stock superpowers **or** this fork
— never both (they define the same skill names).

## How to refresh against a new upstream release

Run \`scripts/refresh-superpowers-fork.sh\` (or let the weekly
\`.github/workflows/refresh-superpowers-fork.yml\` do it and open a PR). The script re-copies the
plugin essentials, re-applies the path convention, re-appends the team workflow overlays, bumps the version, and updates this file.
EOF

echo "Rebuilt wp-labs-superpowers at version $new_version (upstream sha $upstream_sha)"
