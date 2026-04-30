# Findings

Severities follow `agents/docs/code-review/deliverables.md`: `critical · high · medium · low · info`.

## F-001 – Dead helpers left in `handlers.py` after `_format_with_template` rewrite

| Field | Value |
|---|---|
| Severity | medium |
| Location | `sdk/agenta/sdk/engines/running/handlers.py:159-197` |
| Criteria | [general.md – Dead/duplicated code](../../../../../agents/docs/code-review/rubrics/general.md), [sdk.md – Maintainability](../../../../../agents/docs/code-review/rubrics/sdk.md) |

**Condition.** After the rewire, `_format_with_template` no longer calls the module-local `extract_placeholders`, `coerce_to_str`, `build_replacements`, or `missing_lib_hints`. Grep confirms there is no other caller inside `handlers.py` (the `_coerce_to_str` used by similarity evaluators at line 2148 is a separate private helper). No external module imports them from `handlers` — see search at lines 1-23 below.

```text
$ grep -n "extract_placeholders\|build_replacements\|missing_lib_hints" sdk/agenta/sdk/engines/running/handlers.py
159:def extract_placeholders(template: str) -> Iterable[str]:
172:def build_replacements(
185:    replacements[expr] = coerce_to_str(val).replace("\\", "\\\\")
191:def missing_lib_hints(unreplaced: set) -> Optional[str]:
```

The module-level docstring of `templating.py:1-12` claims it is "the single place where the per-mode substitution logic lives," which is contradicted by the leftover copies.

**Cause.** Phase 2 vendored the substitution logic into `templating.py` instead of importing the existing helpers in place; the originals in `handlers.py` were never deleted.

**Consequence.**
- Three near-duplicates of the same algorithm now live in the SDK (`utils/types.py`, `utils/resolvers.py`/local copies in `handlers.py`, and the new `utils/templating.py`).
- WP-B2 work is set up to re-touch this surface; if the judge ever falls back to the local helpers (e.g. an accidental recovery path), behavior could drift from the helper.
- New contributors will reasonably copy these `Public-looking` helpers into other handlers, recreating the divergence the helper was supposed to end.

**Evidence.** `handlers.py:159-197` (definitions); diff for `handlers.py:200-227` shows the helper is now the only path used; grep for the public names returns only `handlers.py` itself plus tests.

**Remediation.**
- **Option A (preferred).** Delete `extract_placeholders`, `coerce_to_str`, `build_replacements`, and `missing_lib_hints` from `handlers.py`. Drop the now-orphaned `Iterable[str]` import if unused. This is a pure removal — covered by the existing tests.
- **Option B.** If there is concern about external callers, leave a `# DEPRECATED` shim that delegates to `templating.py` (or `utils/resolvers.py`) and add an `__all__` excluding them so the surface is documented as internal.

---

## F-002 – `templating.py` re-implements resolvers that already live in `utils/resolvers.py`

| Field | Value |
|---|---|
| Severity | low |
| Location | `sdk/agenta/sdk/utils/templating.py:38-104` |
| Criteria | [general.md – DRY / single source of truth](../../../../../agents/docs/code-review/rubrics/general.md), [sdk.md – Layering](../../../../../agents/docs/code-review/rubrics/sdk.md) |

**Condition.** `templating.py` defines `_detect_scheme`, `_resolve_dot_notation`, `_resolve_json_path`, `_resolve_json_pointer`, and `_resolve_any` (lines 41-104). Identical logic is already exposed by `sdk/agenta/sdk/utils/resolvers.py:19-87` as `detect_scheme`, `resolve_dot_notation`, `resolve_json_path`, `resolve_json_pointer`, `resolve_any` — and that module was created precisely so callers in `utils/` can share resolution logic without an upward import (see its module docstring).

The vendoring comment at `templating.py:38` ("Vendored from utils.types so the helper has no upward import") only addresses `utils/types.py` and overlooks `utils/resolvers.py`, which has no upward dependency either.

**Cause.** The refactor copied the resolver code from `utils/types.py` rather than reusing `utils/resolvers.py`.

**Consequence.** Now three implementations of the same scheme/dot/json-path/json-pointer logic exist:
1. `utils/resolvers.py` — used by the workflow handlers' `resolve_any`/`resolve_json_path` paths.
2. `utils/types.py` — used by `PromptTemplate.build_replacements`.
3. `utils/templating.py` — used by both call sites' new substitution path.

A future bug fix in one will not propagate to the others. WP-B2/B3 will compound this if not addressed now.

**Remediation.**
- **Option A (preferred).** Replace `templating.py:41-104` with `from agenta.sdk.utils.resolvers import resolve_any` and keep only the local `_coerce_to_str`/`_missing_lib_hint`/`_PLACEHOLDER_RE`-based curly logic. Drop the `_detect_scheme`/`_resolve_*` block.
- **Option B.** Defer to WP-B2 and add a `# TODO(WP-B2)` comment plus an entry in the WP-B2 doc to consolidate. Acceptable only if WP-B2 lands soon; otherwise accept Option A now.

---

## F-003 – Misleading import comment in `templating.py`

| Field | Value |
|---|---|
| Severity | low |
| Location | `sdk/agenta/sdk/utils/templating.py:28-31` |
| Criteria | [general.md – Comment accuracy](../../../../../agents/docs/code-review/rubrics/general.md) |

**Condition.**

```python
from agenta.sdk.utils.helpers import (
    apply_replacements_with_tracking,
    _PLACEHOLDER_RE,  # noqa: F401  -- re-exported indirectly via build_replacements
)
```

`_PLACEHOLDER_RE` is used directly at `templating.py:136` (`for match in _PLACEHOLDER_RE.finditer(template)`), and `build_replacements` is not imported into this module. The `# noqa: F401` and the "re-exported indirectly" wording are both incorrect.

**Cause.** Comment likely carried over from an earlier iteration where the import was unused.

**Consequence.** Misleads future readers; the next person to add a real `noqa: F401` will mistakenly reuse the comment pattern.

**Remediation.** Drop the `# noqa: F401` and the comment. The line should read `_PLACEHOLDER_RE,`.

---

## F-004 – `_load_jinja2()` called twice per Jinja render in `handlers._format_with_template`

| Field | Value |
|---|---|
| Severity | low |
| Location | `sdk/agenta/sdk/engines/running/handlers.py:216-219` |
| Criteria | [performance.md – Avoid redundant work on hot paths](../../../../../agents/docs/code-review/rubrics/performance.md) |

**Condition.** The handler loads Jinja2 once just to obtain the `TemplateError` class for the `except` clause, then `render_template(mode="jinja2")` reloads it inside `_render_jinja2`. Negligible CPU cost, but it duplicates the lazy-import bookkeeping and creates a second copy of the sandboxed environment per call.

**Cause.** The exception class is needed at the call site to preserve the judge's silent-return behavior, but the helper does not surface it.

**Consequence.** Minor: extra dictionary lookup per Jinja render. Mostly a code-smell — the call site reaches into Jinja internals just to catch.

**Remediation.**
- **Option A.** Have the helper raise a small local exception type (e.g., `RenderError`) wrapping `TemplateError`, or expose `JINJA_TEMPLATE_ERROR` at module level so callers `from agenta.sdk.utils.templating import JinjaTemplateError`.
- **Option B.** Catch `Exception` at the call site and log it. Slightly broader but acceptable given the silent-return behavior is already a fallback.
- **Option C.** Accept as-is; revisit in WP-B2 when error semantics get aligned.

---

## F-005 – `_coerce_to_str` does a lazy `import json` inside the function body

| Field | Value |
|---|---|
| Severity | info |
| Location | `sdk/agenta/sdk/utils/templating.py:110-120` |
| Criteria | [general.md – Style consistency](../../../../../agents/docs/code-review/rubrics/general.md), `AGENTS.md` § _"Avoid local imports inside helper functions"_ |

**Condition.** `import json` lives inside `_coerce_to_str`. `json` is stdlib and is imported at module top elsewhere in the same package (`utils/types.py:1`). The repo's `AGENTS.md` discourages function-local imports for non-circular cases.

**Remediation.** Move `import json` to the top of `templating.py`.

