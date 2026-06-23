# Drop the commit-hash line from the commit-doc hook

**Date**: 2026-06-23-1155

Logic: The generated doc's `**Commit**: <hash>` line recorded the PRE-amend
short hash (the hook amends the doc into the commit, changing the SHA), so the
recorded hash never matched the final commit and was actively misleading. The
rest of the doc already duplicates the commit subject/body, and the real hash
is available from git — so the line added only wrong data. Removed it (and the
now-unused HASH capture + the SC2016 workaround it required). Kept the
intended subject/date/body doc trail. Mirrored in the global hook.

Caveats/assumptions:
- Existing generated docs still show their old (stale) Commit line; only new
  docs are affected.
