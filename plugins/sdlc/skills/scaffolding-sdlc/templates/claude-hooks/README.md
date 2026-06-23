# claude-hooks/post_commit_doc.sh

A **Claude Code `Stop` hook** (not a git hook). The Claude Code harness runs it
when the agent finishes responding — so it can read `session_id` and amend the
commit. Git never invokes it; it only fires when Claude commits.

**Install:** copy `post_commit_doc.sh` into the repo's `.claude/hooks/` and merge
`settings-hooks.json` into `.claude/settings.json`. The command path is relative
(`bash .claude/hooks/post_commit_doc.sh`).

**Behavior:** after Claude commits, generates `docs/YYYY-MM-DD-HHmm_<slug>.md`
from the commit subject/body (+ optional session summary) and amends it into the
commit. Skips doc-only commits and commits that already contain a generated doc.
