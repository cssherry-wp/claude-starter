---
name: typescript-style
description: JavaScript, TypeScript & React standards. Use when writing, editing, or reviewing .js/.ts/.jsx/.tsx files — covers AI-prone mistakes, TypeScript preferences, React rules, and architecture.
---

# JavaScript, TypeScript & React Rules

*Biome handles all formatting (quotes, semicolons, trailing commas, whitespace), imports (ordering, dedup), naming conventions, and linting (`===`, no `var`, unused vars, curly braces). See the `general-coding-guidelines` skill for general rules.*

## AI-Prone Mistakes — Always Avoid

- **Never use `any`** — prefer `unknown` when the type is truly unknown
- **Never use `eval()`**, `new Function()`, or innerHTML with user data (XSS)
- **Never use synchronous blocking calls** (`fs.readFileSync`, `execSync`) — always use async variants
- **No arrow functions in class fields** — use constructor binding or bind in JSX

## TypeScript Preferences

- **Prefer interfaces over type literals** for object shapes and public contracts
- **Avoid type assertions** (`as Foo`, non-null `!`) without explanatory comments
- Named imports preferred; no wildcard imports

## React-Specific

- **One component per file** (`.jsx`/`.tsx`). Filename matches component name.
- **Co-locate tests**: `Button.jsx` → `Button.test.jsx` in the same directory
- **Destructure props** in function signature with descriptive names for booleans (`isVisible`, `hasPermission`)
- **Never use array index as key** — use stable unique IDs
- **Don't spread props unnecessarily** — pass explicit props
- **Clean up effects** (timers, listeners) and ensure correct dependency arrays

## Architecture

- Resolve data in router before navigation to prevent render flicker
- Keep models, controllers, services in separate files
- Prefer pure functions over side-effecting ones where possible
