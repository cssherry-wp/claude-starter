---
name: css-style
description: CSS/SCSS/Sass style rules. Use when writing, editing, or reviewing stylesheets (.css/.scss/.sass) — follows the Airbnb CSS Style Guide and BEM methodology, and prefers SCSS.
---

# CSS / SCSS Style Rules

## Ground Rule

Follow the Airbnb CSS Style Guide and BEM methodology.

## Syntax Choice
- **Prefer SCSS (`.scss`)** over plain CSS or the indented Sass (`.sass`) syntax.
- Author new stylesheets as `.scss`; when touching an existing plain-CSS file, migrate to SCSS only if it's in scope (Boy Scout Rule — keep it small).
- Use SCSS features (variables, nesting, mixins, partials) to keep styles DRY — but don't over-nest; deep nesting hurts readability and specificity.

## Additional Rules
- Prefer flexbox to lots of CSS hacks.
