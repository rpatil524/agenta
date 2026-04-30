# Status

## Current state

WP-B1 is the first work package from the [RFC](../README.md). Scope is the judge backend patch (provider/secret resolution + temperature removal), the low-level rendering helper extraction, and the companion frontend evaluator-model transform robustness. The earlier idea of broadening LLM-as-a-judge with `llm_config` controls is explicitly out of scope.

## Progress log

- 2026-04-29: Created the planning workspace (then named `llm-judge-chat-unification/`).
- 2026-04-29: Reviewed `auto_ai_critique_v0`, `completion_v0`, `chat_v0`, `PromptTemplate`, `SecretsManager`, and the evaluator frontend transforms.
- 2026-04-29: Captured the implementation plan and QA strategy.
- 2026-04-29: Addressed PR review feedback: removed planned judge temperature injection, added compatibility guidance for future optional LLM parameters, added `variable-and-template-analysis.md`.
- 2026-04-30: Drafted [RFC](../README.md) covering variable handling, JSON preservation, template formats, playground UX, and runtime unification.
- 2026-04-30: Resolved review comments and locked the RFC's work-package layering (backend foundations → mustache → frontend → docs).
- 2026-04-30: Renamed the design workspace to `prompt-runtime-unification/` and moved this WP-B1 content under `wp-b1-runtime-foundation/`. Aligned `plan.md`, `implementation-notes.md`, `qa.md`, and `variable-and-template-analysis.md` with the new RFC's WP-B1 scope.

## Decisions

- Preserve the flat LLM-as-a-judge parameter contract.
- Preserve the LLM-as-a-judge output shape.
- Fix model support by reusing `SecretsManager.get_provider_settings_from_workflow(model)`, not by migrating the judge to a new config shape.
- Keep companion frontend work limited to evaluator model-selection transform robustness. No new judge UI controls.
- Do not inject `temperature` into the judge runtime call. Model/provider compatibility outweighs preserving the current unsupported optional kwarg.
- Extract a low-level rendering helper with signature `(template_string, mode, context) -> rendered_string`. Pure, unit-testable, no service knowledge. Foundation for WP-B2 and WP-B3.
- Primary automated coverage is SDK unit tests and pure frontend transform tests; full custom-provider execution stays as manual/acceptance follow-up unless stable credentials exist.

## Blockers

None for WP-B1.

## Open questions

- Where should the low-level rendering helper live? Options: a new module under `sdk/agenta/sdk/utils/` (close to existing `PromptTemplate`), or alongside the running handlers in `sdk/agenta/sdk/engines/running/`. Decision needed before Phase 2 starts.
- Is there an existing SDK/runtime test suite suitable for mocking `SecretsManager` and the LLM call boundary, or should focused tests be added with local monkeypatching?
- Which runner should own the colocated `web/packages/agenta-entities` unit test for the evaluator transform if no package-level test command currently exists?

## Next steps

1. Implement Phase 1: patch `auto_ai_critique_v0` for shared provider resolution, remove `temperature=0.01`. Add the SDK unit tests in `qa.md`.
2. Land the companion frontend transform tests so custom-model selections persist correctly.
3. Implement Phase 2: extract the low-level rendering helper. Add the helper unit tests and the call-site behavior-preservation tests.
4. Hand off to WP-B2 (message renderer + JSON-return renderer + Jinja error alignment) once the helper is in place.
