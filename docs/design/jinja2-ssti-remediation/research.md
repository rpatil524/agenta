# Research

## Findings

### Current vulnerable rendering

- `sdk/agenta/sdk/workflows/handlers.py` uses `_format_with_template(..., format="jinja2", ...)` and renders via `Template(content).render(**kwargs)`.
- `sdk/agenta/sdk/types.py` uses `PromptTemplate._format_with_template(...)` and renders via `Template(content).render(**kwargs)`.

### Shared lazy loader

- `sdk/agenta/sdk/utils/lazy.py` currently provides `_load_jinja2()` and returns `(Template, TemplateError)`.
- Both vulnerable call sites use this loader.

### Server-reachable path

- Evaluator execution in API routes invokes SDK handlers through `retrieve_handler(...)`.
- `auto_ai_critique_v0` reaches `_format_with_template` in `sdk/agenta/sdk/workflows/handlers.py`, so this path is server-side in platform deployments.

## Security note on advisory accuracy

- Advisory references `api/oss/src/services/evaluators_service.py`, but that file/path no longer exists.
- Real vulnerable paths are in SDK files above.
- Scope should be described as platform deployment surface (self-hosted and managed), not a pure local-library-only issue.
