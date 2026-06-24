# Review skills map

Which reviewer to reach for, and how they hand off.

| Skill | Lane | Editable here |
|---|---|---|
| `change-review` | Broad checklist + dispatch to the deep passes; `--fix`/`--comment`/`--effort` | yes (this plugin) |
| `/code-review` (built-in) | Deep correctness + reuse/simplification/efficiency on the working diff | no |
| `/security-review` (built-in) | Deep vulnerability audit of branch changes | no |
| `/review` (built-in) | Generic GitHub PR review | no |
| `code-review` plugin (`anthropics/claude-code`) | PR-by-number, 5 specialized agents, confidence scoring | no (third-party) |
| `requesting-code-review` | Process: ask for a review before merge | yes |
| `receiving-code-review` | Process: handle review feedback | yes |
| `github-pr-prepare` | Mechanics: open a PR | yes |
| `github-pr-review` | Plumbing: reply to / resolve PR comment threads | yes |

## Hand-off chain

`change-review` (broad scan; dispatches the deep passes)
→ `/code-review` (deep correctness) and `/security-review` (deep security)
→ `requesting-code-review` → `github-pr-prepare` → `receiving-code-review`
→ `github-pr-review` (resolve the resulting threads).

## Naming collision

Three different things sit near the name "code-review":

- **`/code-review`** (built-in) — reviews the **working diff** for correctness + code quality;
  effort tiers; `--fix`/`--comment`. This is what `change-review` calls for deep correctness.
- **`code-review` plugin** (`anthropics/claude-code`) — reviews a **PR by number** with 5 agents
  and confidence scoring. Still exists, but `change-review` now absorbs its unique angles
  (git-history context, prior-PR-comment continuity, inline-comment guidance, confidence scoring),
  so the team review flow and CI no longer use it. Disable it if the duplicate name causes confusion.
- **`change-review`** (this plugin) — the broad dispatcher described above.
