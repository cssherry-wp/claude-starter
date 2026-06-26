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
