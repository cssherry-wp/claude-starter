---
name: general-coding-guidelines
description: General coding standards for any code. Use whenever writing, reviewing, or refactoring code in any language — covers KISS, clean code, function length, logging/observability, testing, docs, and security expectations.
---

# AI Coding Guidelines

## General Principles

### KISS Principle
Avoid overcomplicated code for the sake of brevity or to cover some esoteric edge case that will only show up in a parallel universe. Keep the code simple for someone else to understand. It also reduces chances of introducing bugs.

### Minimal, But Complete

Always be minimal, but complete. Do not add details that are easy to find elsewhere (avoid "AI slop" - for example, PR description should not show the list of files changed, which can be seen in the commit details. It's better to use references than duplicating the content - for example, both humans and AI agents can be expected to know what KISS is, no need to explain in detail.)

### Boy Scout Rule
Existing codebase will often violate clean code principles. Minor cleanups and refactors are welcome, but keep them small, limiting the scope for easier review.

### Clean Code
Read and adhere to Bob Martin's great book, especially SOLID design principles.

### Automate What You Can
Decrease our own workload - both human and AI. That is, do not expect users to
provide input if it can be figured out automatically. Do not make developers do
extra work when it can be automated.

### Logging & Observability
- Instrument code with the **OpenTelemetry framework** (the OTel SDK + instrumentation libraries) to emit logs, traces, and metrics. Don't hand-roll logging/tracing infrastructure — go through OTel so signals export to any backend.
- Follow **OpenTelemetry semantic conventions** for span and attribute names; this also gives you structured, key/value output and automatic trace/span context propagation, so logs correlate with traces without manual plumbing.
- Attach business identifiers (request/entity IDs, operation name) as attributes.
- Log at the right level: `debug` for diagnostics, `info` for meaningful state changes, `warn` for recoverable problems, `error` for failures that need attention.
- Make messages actionable — say what happened and what to check, not just "error".
- Never log secrets, tokens, credentials, or PII.
- Avoid logging in tight loops or hot paths without throttling or sampling.

## Coding Conventions

### Function Length
Hand-written (i.e., non-generated) functions should be shorter than 40 lines. If it gets longer: extract functions.

### Commented Out Code
Remove it. (Should you need to preserve a valuable algorithm, make it conditional and ensure the condition is disabled by default.)

### DIY or 3rd Party
Avoid importing new libraries/tools if you can achieve your objectives with a few lines of code. Two main downsides of bringing in external code:
1. Increases the "unknowns" and thus chances of introducing bugs
2. Makes it harder for other engineers to come in and quickly get a grasp of the code

### Lock Down Everything
Third-party software we use is outside of our control. Lock the version to avoid "surprises". (E.g., use `yarn.lock` and `go.mod`.)

### Model Conventions
- Models' first parameter should generally be the id.
- Model method names should not stutter, i.e. not `users.getUser()`, just `users.get()`.
- Do not pass `req` into any models.

### Performance
SQL in loops: be very careful about SQL within a loop or something like `dbToProject` (DB calls are expensive).

### Naming Conventions
- JSON uses underscores, JavaScript uses camelCase. You should never have underscores in a variable name, but sometimes it's ok as a property. Only do that as a shortcut to encoding/decoding JSON though.
- URLs/routes should use dash not underscore to denote spaces.

### API Versioning
When writing versioned APIs, be sure that older versions continue to function exactly as before. If that is not possible, respond with a clear error message.

### Language Selection
Start projects in safe languages like Go (preferred for backend), TypeScript (preferred for front-end), or Python with type annotations (scripts and utilities).

### Immutability
- Functions should never mutate their arguments.
- Do not mutate or reassign anything that's visible from an outer scope. Among other things, that means don't use non-constant globals.

## Testing

### Always Add Tests
For every feature added or bug fixed, add unit tests covering the core logic and functional/integration tests covering the end-to-end behavior.

### Co-locate Tests With Source
Keep the test file next to the source file in every language:
- JavaScript/React: `Button.test.jsx` next to `Button.jsx`
- Go: `foo_test.go` next to `foo.go`
- Python: `test_foo.py` next to `foo.py`

### Test Invalid Input
Always include tests for edge cases and invalid input, not just the happy path.

## Documentation

### Keep README and Docs Updated
When adding features, changing behavior, or modifying configuration, update `README.md` or any relevant docs in the project. Docs should reflect the current state of the code — stale docs are worse than no docs.

## Security

### Always Code with Security in Mind

**NEVER, EVER, add confidential information to the code.**

Use "secrets" on GitHub or Jenkins that will be passed as environment variables to the code.

### Essential Security Practices

1. **Escape and sanitize user and API input** (including file uploads) - and always test with invalid input
2. **Take special care when executing system commands**
3. **Use prepared SQL statements** instead of string concatenation
4. **Use the principle of least privilege** (logging-secrets guidance lives under Logging & Observability)
