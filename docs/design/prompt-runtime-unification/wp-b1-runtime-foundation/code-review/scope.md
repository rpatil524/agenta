# Scope

## What is being reviewed

WP-B1 runtime foundation changes on branch `feat/llm-judge-chat-unification`:

- `sdk/agenta/sdk/engines/running/handlers.py` — `auto_ai_critique_v0` provider/secret resolution rewrite + temperature removal; `_format_with_template` rewired to call the shared helper.
- `sdk/agenta/sdk/utils/types.py` — `PromptTemplate._format_with_template` rewired to call the shared helper.
- `sdk/agenta/sdk/utils/templating.py` (new) — low-level `render_template(*, template, mode, context) -> str` helper for `curly`, `fstring`, `jinja2`.
- `sdk/oss/tests/pytest/unit/test_auto_ai_critique_v0_runtime.py` (new) — judge handler unit tests.
- `sdk/oss/tests/pytest/unit/test_render_template_helper.py` (new) — helper + call-site behavior preservation tests.
- `docs/design/prompt-runtime-unification/wp-b1-runtime-foundation/status.md` — progress log update.

## Goals

1. Verify the judge backend now resolves provider/secret settings through `SecretsManager.ensure_secrets_in_workflow()` + `SecretsManager.get_provider_settings_from_workflow(model)` and that custom/self-hosted models reach the LLM call.
2. Confirm `temperature=0.01` is no longer sent on the judge LLM call.
3. Validate that the helper extraction preserves the prior public behavior of `PromptTemplate.format` and `_format_with_template`.
4. Verify the helper boundary is consistent with the design (pure, mode-dispatching, no service knowledge).
5. Verify the new tests cover the cases enumerated in `qa.md` and pass.
6. Flag dead code, unnecessary duplication, or behavioral drift that should not be merged into `main`.

## Out of scope (per the WP-B1 RFC)

- Message-list rendering and JSON-return / `response_format` rendering (WP-B2).
- Jinja error alignment across services (WP-B2).
- `mustache` mode (WP-B3).
- Frontend evaluator UX beyond the existing transform check (WP-F1/2/3).
- Pre-existing handler bugs unrelated to WP-B1 (e.g., the unreachable `bool` branch in `auto_ai_critique_v0` result normalization).

## Branch and references

- Branch: `feat/llm-judge-chat-unification`
- Diff base: working tree vs. `HEAD` (commit `fc74e50b0`).
- Design docs: `docs/design/prompt-runtime-unification/wp-b1-runtime-foundation/{plan,implementation-notes,qa,status}.md`.
