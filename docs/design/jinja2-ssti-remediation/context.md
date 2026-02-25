# Context

## Problem Statement

Agenta supports evaluator prompt templating with `template_format="jinja2"`. Current implementation renders untrusted user-controlled templates with `jinja2.Template(...).render(...)` (unsandboxed), which allows SSTI and potential RCE in server contexts.

## Why This Matters

- In managed/multi-tenant environments, authenticated users can potentially execute arbitrary commands through malicious templates.
- In self-hosted usage, risk is lower because authenticated users usually already control the host, but the pattern is still unsafe.

## Goals

- Replace unsandboxed Jinja2 rendering with sandboxed rendering for evaluator formatting paths.
- Preserve existing non-Jinja template behavior (`fstring`, `curly`).
- Keep template-formatting error semantics stable.
- Add regression tests for sandbox behavior.

## Non-Goals

- Reworking evaluator permissions or RBAC model.
- Full redesign of template language support.
- Changes to custom code evaluator enablement policy.
