# Questions

## Q-001 – Should the dead helpers be removed in this PR or deferred to WP-B2?

| Field | Value |
|---|---|
| Status | open |

**Question.** `extract_placeholders`, `coerce_to_str`, `build_replacements`, and `missing_lib_hints` in `sdk/agenta/sdk/engines/running/handlers.py:159-197` are dead after the helper rewire (see F-001). Should they be deleted in WP-B1 or left for WP-B2 alongside the broader handler-side cleanup?

**Why it matters.** Leaving them creates the impression of a public-looking helper inside `handlers.py` that future contributors will copy or import. Deleting now is a one-line change covered by the existing tests; deferring keeps the duplication for at least one more cycle.

**Provisional suggestions.**
- Default to deleting them in this PR. Tests already pass without them.
- If we want to keep the diff strictly Phase-2-extract-only, include a `# TODO(WP-B2): remove once message renderer lands` comment so the residue is intentional, not forgotten.

## Q-002 – Is reuse of `utils/resolvers.py` acceptable for the helper?

| Field | Value |
|---|---|
| Status | open |

**Question.** F-002 recommends replacing the vendored `_detect_scheme`/`_resolve_*` block in `templating.py` with imports from `utils/resolvers.py`. The author's vendoring rationale only mentions `utils/types.py`. Was `utils/resolvers.py` considered, and is there a known reason to keep the helper independent of it?

**Why it matters.** Imports from `utils/resolvers.py` are upward-clean (it has no agenta dependencies beyond `lazy`/`logging`), so the stated "no upward import" goal is already met without copying.
