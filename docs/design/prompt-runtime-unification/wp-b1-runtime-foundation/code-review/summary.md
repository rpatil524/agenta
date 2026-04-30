# Summary

## Overview

- **Reviewed:** WP-B1 (judge backend patch + low-level rendering helper) on `feat/llm-judge-chat-unification`. See `scope.md`.
- **Goals:** confirm provider/secret resolution + temperature removal land cleanly; verify helper extraction preserves behavior; surface dead code, drift risk, and test gaps.
- **Constraints:** WP-B1 deliberately does not touch message-list rendering, JSON-return rendering, Jinja error alignment, or `mustache` (those land in WP-B2/B3).
- **Review type:** SDK code review with light security/test-coverage lens.

## Health verdict

> **PASS WITH CONDITIONS**

The functional change is correct, the test coverage matches `qa.md`, and lint/format are clean. The conditions are housekeeping: remove the dead helpers F-001 left behind in `handlers.py` and (preferably) consolidate the resolver duplication F-002 introduces between `utils/templating.py` and `utils/resolvers.py`. Neither blocks shipping the user-visible fix, but both should be addressed before WP-B2 builds further on this surface.

## Key findings

### Medium

- **F-001 – Dead helpers in `handlers.py`.** `extract_placeholders`/`coerce_to_str`/`build_replacements`/`missing_lib_hints` are no longer reachable from `_format_with_template` and have no external importers. Contradicts `templating.py`'s "single place where mode-specific substitution logic lives" docstring. See `findings.md`.

### Low

- **F-002 – Resolver duplication.** `templating.py` vendors resolvers that already live in `utils/resolvers.py`. Three implementations of the same logic now coexist; WP-B2/B3 will compound the drift if not consolidated.
- **F-003 – Misleading import comment.** `_PLACEHOLDER_RE` is used directly; the `# noqa: F401 -- re-exported indirectly via build_replacements` comment is wrong.
- **F-004 – `_load_jinja2()` called twice on the Jinja path** in `handlers._format_with_template`. Minor.

### Info

- **F-005 – Function-local `import json`** in `_coerce_to_str` violates `AGENTS.md` style guidance.

### Positive observations

- **Behavior is correctly preserved.** New tests pin the call-site contracts: `PromptTemplate` raises `TemplateFormatError` on Jinja sandbox / curly-unresolved / fstring-missing, while the judge keeps its silent-return-on-jinja behavior — both verified explicitly. Pre-existing `test_jinja2_sandbox.py` still passes.
- **Provider resolution path matches `chat_v0`/`completion_v0` shape** (`SecretsManager.ensure_secrets_in_workflow()` → `get_provider_settings_from_workflow(model)` → `mockllm.user_aws_credentials_from(provider_settings)` → `mockllm.acompletion(**provider_settings)`). The judge is no longer an outlier.
- **Security improvement.** Replacing the previous module-level `litellm.openai_key = ...` writes with the per-call `mockllm.user_aws_credentials_from` context manager scrubs ECS/Lambda role environment variables for the duration of the call. This was already the chat/completion pattern; the judge now inherits it. Worth calling out because it's an unstated but real benefit of the rewire.
- **Temperature removal is asserted explicitly** (`test_does_not_send_temperature_in_llm_call`), which makes any future regression visible.
- **Test coverage matches `qa.md` closely.** All Phase-1 and Phase-2 cases listed in `qa.md` have corresponding tests; the only QA-plan item not directly asserted is the manual smoke against a real custom provider — this is intentional and tracked as R-002.
- **Lint/format clean.** `ruff format --check` and `ruff check` pass on the touched files. Full SDK unit suite is green: 248/248.

## Key risks

- **R-001 – Resolver-logic drift across three modules.** Maintainability risk; mitigated by F-002 Option A.
- **R-002 – Manual smoke test still pending.** The custom/self-hosted-model end-to-end check from `qa.md` has not been recorded as run.

## Open questions

- **Q-001:** Should the dead helpers (F-001) be removed in this PR or deferred? Impact: keeps duplication and a misleading public surface.
- **Q-002:** Was `utils/resolvers.py` considered as the import source for the helper instead of vendoring? Impact: determines whether F-002 Option A is acceptable now.

## Coverage and metrics

| Metric | Value |
|---|---|
| Files in scope (production) | 3 (`handlers.py`, `types.py`, `templating.py`) |
| Files in scope (tests) | 2 (`test_auto_ai_critique_v0_runtime.py`, `test_render_template_helper.py`) |
| Files in scope (docs) | 1 (`status.md`) |
| Files reviewed | 6 / 6 |
| Coverage | 100% |
| Critical findings | 0 |
| High findings | 0 |
| Medium findings | 1 |
| Low findings | 3 |
| Info findings | 1 |
| Open questions | 2 |
| Suite status | 248 / 248 passing (`oss/tests/pytest/unit/`) |

## Recommended next steps

1. **(medium)** Delete the dead helpers in `handlers.py:159-197` (F-001). Pure removal — covered by existing tests.
2. **(low)** Replace the vendored resolvers in `templating.py:41-104` with imports from `utils/resolvers.py` (F-002, Option A). Brings the helper's docstring claim ("single place...") in line with reality.
3. **(low)** Run the manual smoke from `qa.md § Acceptance / manual follow-up` against a custom/self-hosted model and append the outcome to `status.md`. This closes R-002 and the user-visible goal of WP-B1.

Optional cleanups (drop into the same PR if convenient): F-003 (misleading comment), F-004 (double `_load_jinja2`), F-005 (function-local `import json`).
