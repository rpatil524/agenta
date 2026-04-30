# Scorecard

| Metric | Value | Note |
|---|---|---|
| Verdict | PASS WITH CONDITIONS | Cleanup of dead helpers + resolver duplication recommended before WP-B2. |
| Critical findings | 0 | |
| High findings | 0 | |
| Medium findings | 1 | F-001 dead helpers in `handlers.py`. |
| Low findings | 3 | F-002 resolver duplication, F-003 stale comment, F-004 double `_load_jinja2`. |
| Info findings | 1 | F-005 function-local `import json`. |
| Open risks | 2 | R-001 resolver drift, R-002 manual smoke pending. |
| Open questions | 2 | Q-001 dead-helper removal scope, Q-002 reuse of `utils/resolvers.py`. |
| Coverage | 100% of in-scope files | 3 production + 2 test + 1 doc. |
| Tests run | 248 / 248 pass | `cd sdk && poetry run pytest oss/tests/pytest/unit/` (8.77s). |
| Lint | clean | `ruff format --check` + `ruff check` on changed files. |
| Behavioral regression risk | low | Existing `test_jinja2_sandbox.py` plus new behavior-preservation tests pin the call-site contracts. |
| Security posture | improved | Per-call `mockllm.user_aws_credentials_from` replaces module-level `litellm.*_key` writes. |
