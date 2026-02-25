# Plan

## Phase 1 - Confirm Attack Surface

1. Locate all Jinja2 render call sites.
2. Confirm which call sites are reachable from server evaluator execution paths.
3. Identify shared utility entry points for minimal-risk fix.

## Phase 2 - Implement Fix

1. Update lazy Jinja2 loader to expose sandboxed environment type.
2. Replace `Template(...).render(...)` with `SandboxedEnvironment().from_string(...).render(...)` in affected paths.
3. Keep current exception handling behavior.

## Phase 3 - Validate

1. Add unit tests proving benign Jinja2 templates still render.
2. Add unit tests proving a known SSTI payload fails safely.
3. Run targeted SDK unit tests.

## Phase 4 - Ship

1. Commit with security-focused message.
2. Push branch and open PR.
3. Provide corrected CVE/GHSA language and scope notes.
