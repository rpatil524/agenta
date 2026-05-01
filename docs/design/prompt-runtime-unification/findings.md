# PR 4231 Synced Findings

> PR: `Agenta-AI/agenta#4231`
> Branch: `feat/llm-judge-chat-unification`
> Base: `main`
> Head synced: `d1862e55f`
> Synced on: `2026-05-01`

## Sources

- GitHub PR `#4231`: `https://github.com/Agenta-AI/agenta/pull/4231`
- GitHub issue `#4244`: `https://github.com/Agenta-AI/agenta/issues/4244`
- GitHub review comments fetched through the GitHub plugin comment surface on `2026-05-01`
- Shared findings references:
  - `agents/skills/shared/references/findings.schema.md`
  - `agents/skills/shared/references/findings.lifecycle.md`
- Local implementation:
  - `docs/design/prompt-runtime-unification/README.md`
  - `docs/design/prompt-runtime-unification/appendix-rendering-edge-cases.md`
  - `docs/design/prompt-runtime-unification/wp-b1-runtime-foundation/plan.md`
  - `sdk/agenta/sdk/engines/running/handlers.py`
  - `sdk/agenta/sdk/litellm/mockllm.py`
  - `sdk/agenta/sdk/utils/types.py`

## Sync Summary

- Re-checked the PR against the local branch on `2026-05-01`.
- One runtime risk called out in PR review is still present in code and is now tracked explicitly by GitHub issue `#4244`: the judge path mutates process-global AWS environment variables across an awaited LLM call.
- Two documentation issues remain open in the prompt-runtime-unification docs: a malformed Markdown table row and stale `api/sdk/...` code-path references.
- One previously reported runtime finding is already fixed in this branch: the guarded `_load_jinja2()` handling in `PromptTemplate._format_with_template`.

## Rules

- `findings.md` is the canonical synced findings record for this PR path.
- Keep all non-findings sections above `Open Findings`.
- Re-check each carried-forward finding against the current branch state before keeping it open.

## Notes

- A GitHub review reply says an external issue was created for the AWS credential-mutation risk, but the risk is still present in this PR branch and remains an open finding here until the code path changes.
- Issue `#4244` captures the intended long-term resolution for the AWS path: remove `os.environ` mutation and pass request-scoped AWS session/client state into the Bedrock/Sagemaker integration.
- I did not include low-value newline-only review comments as findings.

## Open Questions

- None.

## Open Findings

### [OPEN] F1. Judge runtime mutates process-global AWS credentials across an awaited LLM call

- ID: `F1`
- Origin: `sync`
- Lens: `verification`
- Severity: `P1`
- Confidence: `high`
- Status: `open`
- Category: `Correctness`, `Security`, `Compatibility`
- Summary: `auto_ai_critique_v0` wraps `await mockllm.acompletion(...)` inside `mockllm.user_aws_credentials_from(provider_settings)`, and that context manager rewrites `os.environ`. In an async worker, concurrent judge calls can observe or overwrite each other's AWS credentials.
- Evidence:
  - [handlers.py](/Users/junaway/Agenta/github/vibes.worktrees/llm-workflow-unification/sdk/agenta/sdk/engines/running/handlers.py:1020) keeps the credential-mutation context open across the awaited completion call.
  - [mockllm.py](/Users/junaway/Agenta/github/vibes.worktrees/llm-workflow-unification/sdk/agenta/sdk/litellm/mockllm.py:42) mutates process-global environment variables in `user_aws_credentials_from`.
  - PR review comment `3172964744` raised the same risk, and the follow-up only notes that an issue was filed rather than a branch fix.
  - GitHub issue `#4244` documents the same concurrency hazard, scope, and acceptance criteria for removing `user_aws_credentials_from`.
- Files:
  - `sdk/agenta/sdk/engines/running/handlers.py`
  - `sdk/agenta/sdk/litellm/mockllm.py`
- Cause: Provider credentials for AWS-backed custom models are injected through process-global environment variables instead of request-scoped client configuration.
- Explanation: This is safe only if nothing else can run through the same process while the `await` is suspended. That is not a sound assumption for async workers. The failure mode is cross-request credential bleed for self-hosted/custom AWS providers.
- Suggested Fix:
  - Remove the env-based credential handoff from the awaited call path.
  - Prefer request-scoped credential injection into the LiteLLM/client layer.
  - Align the implementation with issue `#4244` acceptance criteria: no process-global env mutation during LLM calls, remove `user_aws_credentials_from` and related env-key helpers, and preserve Bedrock/Sagemaker behavior under ECS/Lambda role deployments.
  - If that cannot land in this PR, serialize the AWS credential mutation path as a stopgap and keep the issue open until the durable fix lands.
- Alternatives:
  - Leave this PR as-is and track the fix only in the follow-up issue. That reduces branch scope but leaves a real concurrency risk in the merged runtime.
- Sources:
  - GitHub PR comment `3172964744`
  - GitHub PR reply `3173028409`
  - GitHub PR reply `3173029226`
  - GitHub issue `#4244`

### [OPEN] F2. Rendering appendix still has a malformed Markdown table row

- ID: `F2`
- Origin: `sync`
- Lens: `verification`
- Severity: `P3`
- Confidence: `high`
- Status: `open`
- Category: `Documentation`, `Completeness`
- Summary: The final row in the rendering edge-cases table contains an unescaped pipe in Jinja syntax, so the row has the wrong column count and renders incorrectly.
- Evidence:
  - [appendix-rendering-edge-cases.md](/Users/junaway/Agenta/github/vibes.worktrees/llm-workflow-unification/docs/design/prompt-runtime-unification/appendix-rendering-edge-cases.md:336) contains ``{{ context | tojson }}`` inside a table cell without escaping `|`.
  - GitHub review comment `4210927738` flagged the same Markdown issue.
- Files:
  - `docs/design/prompt-runtime-unification/appendix-rendering-edge-cases.md`
- Cause: Markdown table syntax is being used with raw Jinja filter syntax in the cell body.
- Explanation: This is a doc-only issue, but it breaks the rendered guidance exactly where the document is trying to show escaping and rendering rules.
- Suggested Fix:
  - Escape the pipe in the Jinja example or rewrite the sentence so the row stays at two columns.
- Alternatives:
  - Move the Jinja example out of the table into a short fenced snippet below it.
- Sources:
  - GitHub PR review comment `4210927738`

### [OPEN] F3. RFC current-state section still points to obsolete `api/sdk/...` paths

- ID: `F3`
- Origin: `sync`
- Lens: `verification`
- Severity: `P3`
- Confidence: `high`
- Status: `open`
- Category: `Documentation`, `Maintainability`
- Summary: The main RFC still references SDK runtime files under `api/sdk/...`, but the actual files in this repository live under `sdk/agenta/sdk/...`.
- Evidence:
  - [README.md](/Users/junaway/Agenta/github/vibes.worktrees/llm-workflow-unification/docs/design/prompt-runtime-unification/README.md:36) references `api/sdk/agenta/sdk/types.py`.
  - [README.md](/Users/junaway/Agenta/github/vibes.worktrees/llm-workflow-unification/docs/design/prompt-runtime-unification/README.md:42) references `api/sdk/agenta/sdk/workflows/handlers.py`.
  - The corresponding live files are [types.py](/Users/junaway/Agenta/github/vibes.worktrees/llm-workflow-unification/sdk/agenta/sdk/utils/types.py) and [handlers.py](/Users/junaway/Agenta/github/vibes.worktrees/llm-workflow-unification/sdk/agenta/sdk/engines/running/handlers.py).
- Files:
  - `docs/design/prompt-runtime-unification/README.md`
- Cause: The RFC text was not updated after the SDK/runtime code moved to the current repo layout.
- Explanation: This does not break runtime behavior, but it weakens the RFC as a source-of-truth document because readers are sent to nonexistent or obsolete paths when validating the design against implementation.
- Suggested Fix:
  - Update the path references in the RFC to the current `sdk/agenta/sdk/...` locations.
  - Audit the rest of `docs/design/prompt-runtime-unification` for the same stale path pattern.
- Alternatives:
  - Omit file paths from the RFC entirely. That reduces drift risk but also makes the document less auditable.
- Sources:
  - Local branch inspection on `2026-05-01`

## Closed Findings

### [CLOSED] F4. `_load_jinja2()` masking in `PromptTemplate._format_with_template`

- ID: `F4`
- Origin: `sync`
- Lens: `verification`
- Severity: `P2`
- Confidence: `high`
- Status: `fixed`
- Category: `Correctness`, `Robustness`
- Summary: The earlier PR review concern that `_load_jinja2()` could mask the original formatting exception is already fixed in this branch.
- Evidence:
  - [types.py](/Users/junaway/Agenta/github/vibes.worktrees/llm-workflow-unification/sdk/agenta/sdk/utils/types.py:732) now wraps `_load_jinja2()` in `try/except ImportError` before checking `TemplateError`.
  - `git log --grep='Guard _load_jinja2'` shows commit `477ee62f4`.
- Files:
  - `sdk/agenta/sdk/utils/types.py`
- Cause: The original implementation called `_load_jinja2()` unguarded inside a broad exception handler.
- Explanation: The current branch no longer has that failure mode, so this item should not remain open in the synced record.
- Suggested Fix:
  - None.
- Alternatives:
  - None.
- Sources:
  - GitHub PR comment `3170264586`
  - Local branch inspection on `2026-05-01`
