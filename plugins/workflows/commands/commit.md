---
description: Create a git commit using the team's structured commit-message format.
allowed-tools: Bash(git add:*), Bash(git commit:*), Bash(git status:*), Bash(git diff:*), Bash(git log:*)
---

Create a git commit for the current changes following the team commit policy.

## Steps

1. Run `git status` and `git diff` (and `git diff --staged`) to see what changed.
2. Stage the relevant changes if not already staged.
3. If on the default branch (`main`/`master`), create a feature branch first.
4. Write the commit message in the format below and commit.

## Commit message format

```
<subject line>

Logic
<reason for the change — the problem being solved or goal achieved>

What this adds
- <brief but thorough bullets describing what the change introduces>
- <scope and user-visible/behavioral effect>

Notable design decisions
- <decision and the rationale behind it>

Alternatives considered
- <option A>: <why rejected>
- <option B>: <why rejected>

Test
- <how the change was verified — commands run, environments, results; or state plainly
  if it was not tested and why>

Caveats/assumptions
- <item>
```

## Rules

- **Subject line**: concise summary of what changed, 50 characters max.
- **Logic**: why this change was made.
- **What this adds**: brief but thorough bullets — fuller than the subject, no padding.
- **Notable design decisions**: significant choices and why (data model, interface, trade-offs);
  omit if the change is trivial.
- **Alternatives considered**: other approaches evaluated and why they were rejected.
- **Test**: how it was verified — actual commands/results, not aspirations. If untested, say so.
- **Caveats/assumptions**: assumptions made, edge cases not handled, or limitations.
- Omit a section only if it genuinely doesn't apply (e.g. no real alternatives for a trivial
  rename, no meaningful caveats). Do not invent content to fill sections.
- Do not commit secrets or unrelated changes.
