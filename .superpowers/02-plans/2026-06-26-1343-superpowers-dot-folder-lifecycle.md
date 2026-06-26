# `.superpowers/` doc paths + spec→issue lifecycle — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move spec/plan output to a hidden `.superpowers/` folder and add a spec→issue→comment→docs lifecycle, applied to both the overlay (`team-docs-convention`) and the auto-refreshing fork (`wp-labs-superpowers`), surviving the weekly refresh.

**Architecture:** Path strings change `docs/01-specs`→`.superpowers/01-specs` and `docs/02-plans`→`.superpowers/02-plans` across skills, the refresh script, and docs. Three new behaviors are stored as delimited overlay fragment files and (a) applied to the committed fork skills now, (b) re-appended idempotently by the refresh script after each upstream rebuild. The overlay skill (`team-docs-convention`) carries the same paths + behaviors as prose for stock-superpowers users.

**Tech Stack:** Markdown skill files, one Bash script (`refresh-superpowers-fork.sh`), `gh` CLI, `shellcheck` for script verification.

## Global Constraints

- Spec path: `.superpowers/01-specs/YYYY-MM-DD-HHmm-<name-of-spec>.md` (24-hour `HHmm`).
- Plan path: `.superpowers/02-plans/YYYY-MM-DD-HHmm-<name-of-plan>.md` (24-hour `HHmm`).
- Overlay fragments are delimited by `<!-- wp-labs team overlay: BEGIN -->` / `<!-- wp-labs team overlay: END -->`.
- `gh` steps must degrade gracefully: if `gh` is missing/unauthenticated, report and continue — never block.
- Do NOT migrate specs/plans already committed under `docs/01-specs` / `docs/02-plans`.
- `.superpowers/sdd/` is out of scope.
- Each task ends with a commit using the team's structured format (subject ≤50 chars; Logic / Alternatives / Caveats body where meaningful).

---

### Task 1: Create the three team-overlay fragment files

**Files:**
- Create: `plugins/wp-labs-superpowers/team-overlays/brainstorming.md`
- Create: `plugins/wp-labs-superpowers/team-overlays/writing-plans.md`
- Create: `plugins/wp-labs-superpowers/team-overlays/finishing-a-development-branch.md`

**Interfaces:**
- Produces: three fragment files, each wrapped in the BEGIN/END markers. The fragment filename (minus `.md`) maps to the skill directory name under `skills/`. Tasks 2 and 3 consume these files.

- [ ] **Step 1: Create `brainstorming.md`** with exactly this content:

```markdown
<!-- wp-labs team overlay: BEGIN -->

## Team workflow: sync the approved spec to a GitHub issue

After the user approves the written spec (the User Review Gate passes) and BEFORE invoking
writing-plans, link the spec to GitHub issue tracking:

1. **Identify the tracking issue.** The spec derives from an existing issue if the conversation
   or the spec text references one (e.g. `#42` or a GitHub issue URL).
2. **If an existing issue is identified:** append the spec to it as a comment —
   `gh issue comment <number> --body-file <spec-path>`.
3. **If none is identified:** ask the user `Create a GitHub tracking issue for this spec? (Y/n)`.
   On yes (the default), create it with the spec as the body —
   `gh issue create --title "<spec slug>" --body-file <spec-path>`. On no, skip and note that no
   issue is linked.
4. **Record the issue** in the spec file as a `Tracking issue: <url>` line, then commit the spec
   update. writing-plans reads this line to post the plan as a comment.

If `gh` is missing or unauthenticated, report it and continue — never block the workflow on it.

<!-- wp-labs team overlay: END -->
```

- [ ] **Step 2: Create `writing-plans.md`** with exactly this content:

```markdown
<!-- wp-labs team overlay: BEGIN -->

## Team workflow: post the plan to the tracking issue

After the plan file is saved and self-reviewed, post it to the spec's tracking issue:

1. Read the `Tracking issue:` line from the spec this plan is based on.
2. If a tracking issue is present, post the plan as a comment —
   `gh issue comment <number> --body-file <plan-path>`.
3. If the spec has no tracking issue, skip with a one-line note.

If `gh` is missing or unauthenticated, report it and continue.

<!-- wp-labs team overlay: END -->
```

- [ ] **Step 3: Create `finishing-a-development-branch.md`** with exactly this content:

```markdown
<!-- wp-labs team overlay: BEGIN -->

## Team workflow: write feature documentation

After tests pass (Step 1) and before presenting the integration options (Step 4), write
user-facing documentation for the feature you implemented:

1. Review the repo's existing `docs/` folder to match its structure and tone.
2. Write a **task-oriented usage/adaptation guide** in the style of the lumen docs
   (e.g. `adding-a-data-source.md`): a `# Title`, a one-line **Goal:**, then numbered sections
   with concrete steps, commands, and references to real files in the repo. This is a how-to guide
   for using and adapting the feature — NOT a dated changelog.
3. Save it to `docs/<kebab-feature-name>.md` and commit it.

Skip only if the change ships no user- or developer-facing capability (e.g. a pure internal
refactor) — say so explicitly rather than skipping silently.

<!-- wp-labs team overlay: END -->
```

- [ ] **Step 4: Verify each fragment has exactly one BEGIN and one END marker**

Run: `for f in plugins/wp-labs-superpowers/team-overlays/*.md; do echo "$f: $(grep -c 'team overlay: BEGIN' "$f")/$(grep -c 'team overlay: END' "$f")"; done`
Expected: each line shows `1/1`.

- [ ] **Step 5: Commit**

```bash
git add plugins/wp-labs-superpowers/team-overlays/
git commit -m "feat(superpowers): add team workflow overlay fragments"
```

---

### Task 2: Apply path changes + append overlays to the fork skills

**Files:**
- Modify: `plugins/wp-labs-superpowers/skills/brainstorming/SKILL.md` (paths + append `brainstorming.md`)
- Modify: `plugins/wp-labs-superpowers/skills/brainstorming/spec-document-reviewer-prompt.md` (paths)
- Modify: `plugins/wp-labs-superpowers/skills/writing-plans/SKILL.md` (paths + append `writing-plans.md`)
- Modify: `plugins/wp-labs-superpowers/skills/finishing-a-development-branch/SKILL.md` (append `finishing-a-development-branch.md`)
- Modify: `plugins/wp-labs-superpowers/skills/requesting-code-review/SKILL.md` (example path)
- Modify: `plugins/wp-labs-superpowers/skills/subagent-driven-development/SKILL.md` (example path)

**Interfaces:**
- Consumes: the three fragment files from Task 1.
- Produces: fork skills that reference `.superpowers/...` paths and carry the overlay blocks. The refresh script (Task 3) relies on the BEGIN marker already being present to stay idempotent.

- [ ] **Step 1: Substitute paths across all fork skills**

Run:
```bash
grep -rl 'docs/01-specs\|docs/02-plans' plugins/wp-labs-superpowers/skills/ | while IFS= read -r f; do
  sed -i.bak -e 's#docs/01-specs#.superpowers/01-specs#g' -e 's#docs/02-plans#.superpowers/02-plans#g' "$f"
  rm -f "$f.bak"
done
```

- [ ] **Step 2: Verify no old paths remain in fork skills**

Run: `grep -rn 'docs/01-specs\|docs/02-plans' plugins/wp-labs-superpowers/skills/ || echo CLEAN`
Expected: `CLEAN`.

- [ ] **Step 3: Append the three overlay fragments to their target skills**

Run:
```bash
for name in brainstorming writing-plans finishing-a-development-branch; do
  target="plugins/wp-labs-superpowers/skills/$name/SKILL.md"
  if ! grep -q 'wp-labs team overlay: BEGIN' "$target"; then
    printf '\n' >> "$target"
    cat "plugins/wp-labs-superpowers/team-overlays/$name.md" >> "$target"
  fi
done
```

- [ ] **Step 4: Verify each target skill now contains exactly one overlay block**

Run: `for name in brainstorming writing-plans finishing-a-development-branch; do echo "$name: $(grep -c 'team overlay: BEGIN' plugins/wp-labs-superpowers/skills/$name/SKILL.md)"; done`
Expected: each shows `1`.

- [ ] **Step 5: Commit**

```bash
git add plugins/wp-labs-superpowers/skills/
git commit -m "feat(superpowers): .superpowers paths + lifecycle in fork skills"
```

---

### Task 3: Update the refresh script (sed targets + append step + FORK.md heredoc)

**Files:**
- Modify: `scripts/refresh-superpowers-fork.sh`

**Interfaces:**
- Consumes: `plugins/wp-labs-superpowers/team-overlays/*.md` (Task 1), the BEGIN marker convention (Task 2).
- Produces: a refresh that emits `.superpowers/...` paths and re-appends overlays idempotently.

- [ ] **Step 1: Update the path `sed` substitutions**

In the "Apply the team docs-path convention" block, change the replacement targets:
- `docs/01-specs` → `.superpowers/01-specs`
- `docs/02-plans` → `.superpowers/02-plans`

The grep that selects files still matches upstream's `docs/superpowers/\(specs\|plans\)`. After this edit that block reads:

```bash
while IFS= read -r f; do
  sed -i.bak -e 's#docs/superpowers/specs#.superpowers/01-specs#g' \
             -e 's#docs/superpowers/plans#.superpowers/02-plans#g' "$f"
  rm -f "$f.bak"
done < <(grep -rl 'docs/superpowers/\(specs\|plans\)' "$FORK_DIR/skills" 2>/dev/null || true)
```

Also update the two best-effort HHmm `sed` lines to target `.superpowers`:

```bash
sed -i.bak 's#docs/superpowers/specs/YYYY-MM-DD-<topic>-design\.md#.superpowers/01-specs/YYYY-MM-DD-HHmm-<name-of-spec>.md#g' \
  "$FORK_DIR/skills/brainstorming/SKILL.md" 2>/dev/null && rm -f "$FORK_DIR/skills/brainstorming/SKILL.md.bak" || true
sed -i.bak 's#docs/superpowers/plans/YYYY-MM-DD-<feature-name>\.md#.superpowers/02-plans/YYYY-MM-DD-HHmm-<name-of-plan>.md#g' \
  "$FORK_DIR/skills/writing-plans/SKILL.md" 2>/dev/null && rm -f "$FORK_DIR/skills/writing-plans/SKILL.md.bak" || true
```

(The original lines matched `docs/01-specs/...-design.md`; switch them to match the upstream `docs/superpowers/...` source pattern so they fire on a fresh upstream copy.)

- [ ] **Step 2: Add the overlay re-append step**

Immediately after the path-substitution block and before the "Rewrite our plugin manifest" block, insert:

```bash
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
```

Note: the script's `rm -rf "$FORK_DIR/skills" ...` line removes only `skills`, `hooks`, `LICENSE`, `README.md` — `team-overlays/` is untouched and survives the rebuild.

- [ ] **Step 3: Update the FORK.md heredoc's "What diverges" section**

In the `cat >"$FORK_DIR/FORK.md"` heredoc, update the divergence list so item 1 reads:

```
1. **Docs-path convention** applied to the skill text:
   - \`docs/superpowers/specs/...\` → \`.superpowers/01-specs/YYYY-MM-DD-HHmm-<name-of-spec>.md\`
   - \`docs/superpowers/plans/...\` → \`.superpowers/02-plans/YYYY-MM-DD-HHmm-<name-of-plan>.md\`
```

And add a new divergence item:

```
3. **Team workflow overlays** — spec→issue (brainstorming), plan→comment (writing-plans), and
   feature-docs (finishing-a-development-branch) are appended from \`team-overlays/\` after each
   rebuild.
```

- [ ] **Step 4: Lint the script**

Run: `shellcheck scripts/refresh-superpowers-fork.sh`
Expected: no errors (warnings consistent with the pre-existing baseline are acceptable; do not introduce new ones).

- [ ] **Step 5: Dry-run the append logic for idempotency on a scratch copy**

Run:
```bash
SCRATCH=$(mktemp -d)
mkdir -p "$SCRATCH/skills/brainstorming"
echo "# stub skill" > "$SCRATCH/skills/brainstorming/SKILL.md"
cp -R plugins/wp-labs-superpowers/team-overlays "$SCRATCH/team-overlays"
FORK_DIR="$SCRATCH"
OVERLAY_DIR="$FORK_DIR/team-overlays"
apply() { for frag in "$OVERLAY_DIR"/*.md; do [ -e "$frag" ] || continue; sk=$(basename "$frag" .md); t="$FORK_DIR/skills/$sk/SKILL.md"; [ -f "$t" ] || continue; grep -q 'wp-labs team overlay: BEGIN' "$t" || { printf '\n' >>"$t"; cat "$frag" >>"$t"; }; done; }
apply; apply
echo "BEGIN markers after two applies: $(grep -c 'team overlay: BEGIN' "$SCRATCH/skills/brainstorming/SKILL.md")"
rm -rf "$SCRATCH"
```
Expected: `BEGIN markers after two applies: 1`.

- [ ] **Step 6: Commit**

```bash
git add scripts/refresh-superpowers-fork.sh
git commit -m "feat(superpowers): refresh emits .superpowers paths + re-applies overlays"
```

---

### Task 4: Update the overlay skill (`team-docs-convention`) — paths + lifecycle prose

**Files:**
- Modify: `plugins/wp-labs-standards/skills/team-docs-convention/SKILL.md`

**Interfaces:**
- Produces: the overlay source of truth describing the full lifecycle for stock-superpowers users.

- [ ] **Step 1: Replace the paths and substitution note**

Change the two path bullets to:
- `**Specs:** `.superpowers/01-specs/YYYY-MM-DD-HHmm-<name-of-spec>.md``
- `**Plans:** `.superpowers/02-plans/YYYY-MM-DD-HHmm-<name-of-plan>.md``

And in the closing paragraph, change "substitute these paths wherever they reference `docs/superpowers/specs/` or `docs/superpowers/plans/`" to keep referencing the upstream source paths (`docs/superpowers/specs/` / `docs/superpowers/plans/`) — unchanged, since those are upstream's defaults.

- [ ] **Step 2: Append the lifecycle section** to the end of the skill:

```markdown

## Lifecycle: spec → issue → plan-comment → feature docs

These steps apply whether you use stock superpowers or the team fork:

1. **Spec → issue** (after the spec is approved): if the spec derives from an existing GitHub
   issue, append it as a comment (`gh issue comment <n> --body-file <spec>`). Otherwise ask
   `Create a GitHub tracking issue for this spec? (Y/n)` and on yes create it
   (`gh issue create --title "<slug>" --body-file <spec>`). Record `Tracking issue: <url>` in the
   spec and commit.
2. **Plan → comment** (after the plan is saved): read the spec's `Tracking issue:` line and post
   the plan as a comment (`gh issue comment <n> --body-file <plan>`). Skip if no issue is linked.
3. **Implementation → docs** (after implementation completes): write a task-oriented
   usage/adaptation guide for the feature into `docs/<kebab-name>.md` — a how-to guide, not a
   dated changelog.

If `gh` is missing or unauthenticated, report and continue; never block on it.
```

- [ ] **Step 3: Verify paths updated and no stale `docs/01-specs` remain**

Run: `grep -n '\.superpowers/01-specs\|\.superpowers/02-plans' plugins/wp-labs-standards/skills/team-docs-convention/SKILL.md && (grep -n 'docs/01-specs\|docs/02-plans' plugins/wp-labs-standards/skills/team-docs-convention/SKILL.md || echo "NO-STALE")`
Expected: shows the two new `.superpowers` paths, then `NO-STALE`.

- [ ] **Step 4: Commit**

```bash
git add plugins/wp-labs-standards/skills/team-docs-convention/SKILL.md
git commit -m "feat(standards): .superpowers paths + lifecycle in team-docs-convention"
```

---

### Task 5: Update FORK.md and README.md doc references

**Files:**
- Modify: `plugins/wp-labs-superpowers/FORK.md`
- Modify: `README.md`

**Interfaces:**
- Produces: docs that match the new convention. (FORK.md is regenerated by the script on refresh; this edit keeps the committed copy correct in the meantime and must match the heredoc from Task 3.)

- [ ] **Step 1: Update FORK.md "What diverges" item 1** to the `.superpowers/...` paths and add the team-overlays divergence item (mirror the heredoc text from Task 3 Step 3).

- [ ] **Step 2: Update README.md "Docs convention" section** (lines ~108-110) to:

```markdown
Specs go to `.superpowers/01-specs/YYYY-MM-DD-HHmm-<name>.md`; plans to
`.superpowers/02-plans/YYYY-MM-DD-HHmm-<name>.md`.
```

- [ ] **Step 3: Verify**

Run: `grep -rn 'docs/01-specs\|docs/02-plans' README.md plugins/wp-labs-superpowers/FORK.md || echo CLEAN`
Expected: `CLEAN`.

- [ ] **Step 4: Commit**

```bash
git add README.md plugins/wp-labs-superpowers/FORK.md
git commit -m "docs: point fork notes + README at .superpowers paths"
```

---

### Task 6: Version bumps

**Files:**
- Modify: `plugins/wp-labs-superpowers/.claude-plugin/plugin.json` (`6.0.3-team.1` → `6.0.3-team.2`)
- Modify: `plugins/wp-labs-standards/.claude-plugin/plugin.json` (`0.2.0` → `0.3.0`)

**Interfaces:**
- Produces: version strings the team picks up on `/plugin update`.

- [ ] **Step 1: Bump superpowers fork version** to `6.0.3-team.2`.

- [ ] **Step 2: Bump standards version** to `0.3.0`.

- [ ] **Step 3: Verify both manifests are valid JSON**

Run: `for f in plugins/wp-labs-superpowers/.claude-plugin/plugin.json plugins/wp-labs-standards/.claude-plugin/plugin.json; do node -e "JSON.parse(require('fs').readFileSync('$f','utf8')); console.log('$f OK')"; done`
Expected: both print `OK`.

- [ ] **Step 4: Commit**

```bash
git add plugins/wp-labs-superpowers/.claude-plugin/plugin.json plugins/wp-labs-standards/.claude-plugin/plugin.json
git commit -m "chore: bump superpowers + standards plugin versions"
```

---

### Task 7: Final verification sweep

**Files:** none (verification only)

- [ ] **Step 1: Confirm no stale paths anywhere outside historical committed docs**

Run: `grep -rn 'docs/01-specs\|docs/02-plans' plugins/ scripts/ README.md | grep -v '^\.superpowers/' || echo CLEAN`
Expected: `CLEAN` (the only legitimate remaining references are inside `.superpowers/01-specs/` and `.superpowers/02-plans/` history, which the path filter excludes).

- [ ] **Step 2: Re-lint the refresh script**

Run: `shellcheck scripts/refresh-superpowers-fork.sh`
Expected: no new errors.

- [ ] **Step 3: Confirm overlay blocks present once in each fork skill**

Run: `for name in brainstorming writing-plans finishing-a-development-branch; do echo "$name: $(grep -c 'team overlay: BEGIN' plugins/wp-labs-superpowers/skills/$name/SKILL.md)"; done`
Expected: each `1`.

- [ ] **Step 4: Confirm git tree is clean (all work committed)**

Run: `git status --short`
Expected: empty output.

---

## Self-Review

- **Spec coverage:** Goal 1 (paths) → Tasks 2, 3, 4, 5; Goal 2a (spec→issue) → Task 1 + 2 + 4; Goal 2b (plan→comment) → Task 1 + 2 + 4; Goal 2c (impl→docs) → Task 1 + 2 + 4; Goal 3 (refresh survival) → Task 3. Version bumps → Task 6. Verification → Task 7. No gaps.
- **Placeholder scan:** all fragment and edit content is shown verbatim; no TBD/TODO.
- **Consistency:** marker string `wp-labs team overlay: BEGIN` identical across Tasks 1, 2, 3, 7; fragment filenames match skill dir names so the append loop resolves targets correctly.
