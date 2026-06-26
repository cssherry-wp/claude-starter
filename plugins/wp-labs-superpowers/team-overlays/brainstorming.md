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
4. **Record the issue** in the spec file as a `Tracking issue: <url>` line. writing-plans reads
   this line to post the plan as a comment.

Write the spec to the **top-level** repository's `.superpowers/01-specs/` — the main working tree,
not a worktree (resolve via `git -C "$(git rev-parse --git-common-dir)/.." rev-parse --show-toplevel`)
— so it persists across worktrees.

**`.superpowers/` is git-ignored working space — do NOT commit the spec file.** A committed
`.superpowers/.gitignore` keeps the tree out of git; the GitHub issue created/updated above is the
spec's durable record. This overrides any "commit the design document to git" step earlier in this
skill.

If `gh` is missing or unauthenticated, report it and continue — never block the workflow on it.

<!-- wp-labs team overlay: END -->
