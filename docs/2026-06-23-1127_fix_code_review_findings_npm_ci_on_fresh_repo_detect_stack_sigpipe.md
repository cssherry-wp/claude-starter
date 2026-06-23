# Fix code-review findings: npm ci on fresh repo, detect-stack SIGPIPE

**Date**: 2026-06-23-1127  
**Commit**: `e56552b`

Logic: High-effort review of the branch surfaced two issues:
1. [bug] TS Makefile `install` used `npm ci`, which hard-fails on a freshly
   scaffolded repo (no package-lock.json) — the first command a developer runs
   after scaffolding errored out. Switched to `npm install` (creates the lock);
   CI/Docker keep `npm ci` against the committed lock.
2. [latent] detect-stack.sh used `find ... | head -1 | grep -q .` under
   `set -o pipefail`; when find's output exceeds the pipe buffer it is SIGPIPE'd
   (141) and pipefail makes the condition false -> false-negative stack
   detection. Replaced with a `has_file` helper using `find -print -quit`
   (first-match, no full traversal, no SIGPIPE).

Verified: detect-stack shellcheck clean + correct on multi/ts-only/py-only;
fresh TS `make install` succeeds and `make test` passes.
