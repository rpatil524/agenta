# Risks

## R-001 – Three implementations of dot/JSON-path resolution drift over time

| Field | Value |
|---|---|
| Category | Maintainability |
| Likelihood | medium |
| Impact | medium |

**Description.** As of WP-B1 the SDK has three sources of truth for the same substitution logic: `utils/resolvers.py`, `utils/types.py`, and the new `utils/templating.py`. WP-B2 and WP-B3 will add the message renderer, JSON-return renderer, and `mustache` mode on top — every additional consumer multiplies the chance one branch will diverge from the others (e.g., a behavior-affecting fix to JSON-Pointer error handling lands in only one).

**Evidence.**
- `sdk/agenta/sdk/utils/resolvers.py:19-87`
- `sdk/agenta/sdk/utils/types.py:498-610`
- `sdk/agenta/sdk/utils/templating.py:41-128`

**Mitigation options.**
- Consolidate now — see `findings.md` F-002 Option A.
- Add a regression test that runs the same fixture set against `templating.render_template` and `PromptTemplate.format` (already present in `test_render_template_helper.py` for one case) and extend it before WP-B2 lands.

## R-002 – Manual smoke test for custom/self-hosted models is still pending

| Field | Value |
|---|---|
| Category | Validation |
| Likelihood | low |
| Impact | high |

**Description.** Unit coverage exercises the `SecretsManager`/`mockllm` boundary, but the end-to-end "configure custom model in Model Hub → run judge evaluator" smoke test from `qa.md § Acceptance / manual follow-up` has not been recorded as run. The behavioral fix (custom-provider judge support) is the user-visible motivation for WP-B1.

**Mitigation options.**
- Run the manual smoke before merging and record the outcome in `status.md` "Progress log".
- If credentials for a self-hosted provider are unavailable, document the gap explicitly so a follow-up on staging can pick it up.
