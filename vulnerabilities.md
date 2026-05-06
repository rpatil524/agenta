# Dependabot Vulnerability Triage

Snapshot of Dependabot alerts verified against the working tree on 2026-05-06.

This file is split into **Open** (still applicable in the current tree) and **Closed / `done`** (the vulnerable version or scanned lockfile is no longer present; Dependabot should auto-close on its next scan).

## Summary by location

| Location | Alerts | Status |
| --- | --- | --- |
| [api/uv.lock](api/uv.lock), [sdk/uv.lock](sdk/uv.lock), [services/uv.lock](services/uv.lock) - pytest | 3 | open (V007) |
| ~~[web/pnpm-lock.yaml](web/pnpm-lock.yaml) - Next.js~~ | ~~1~~ | **`done`** (V002) |
| ~~[web/pnpm-lock.yaml](web/pnpm-lock.yaml) - axios cluster~~ | ~~15~~ | **`done`** (V001) |
| ~~[web/pnpm-lock.yaml](web/pnpm-lock.yaml) - uuid~~ | ~~1~~ | **`done`** (V006) |
| ~~[docs/pnpm-lock.yaml](docs/pnpm-lock.yaml) + [docs/package-lock.json](docs/package-lock.json)~~ | ~~6~~ | **`done`** (V003-V005) |
| ~~`requirements.test.txt` files~~ | ~~2~~ | **`done`** (V008) |
| ~~api/sdk/services `poetry.lock`~~ | ~~3~~ | **`done`** (V014, lockfiles removed) |
| ~~example app lockfiles~~ | ~~11~~ | **`done`** (V009-V013, lockfiles removed) |

---

## Open

Alerts still requiring dependency or lockfile changes.

### Open - Moderate

#### V007 - pytest tmpdir handling - #643, #644, #645

- **Where:** [api/uv.lock](api/uv.lock), [sdk/uv.lock](sdk/uv.lock), and [services/uv.lock](services/uv.lock) all still resolve `pytest 8.4.2`.
- **Advisory:** GHSA-6w46-j5rx-g56g. Affected: `<9.0.3`. Patched: **9.0.3**.
- **Current state:** The old poetry-side duplicate alerts (#534, #535, #536) are closed by lockfile removal. The three uv-side alerts remain real.
- **Caveat:** The current `pyproject.toml` constraints have already been tightened to `pytest>=9,<10`, but the uv locks have not been regenerated and still show `pytest 8.4.2` plus stale `specifier = ">=8,<10"` metadata. Run the relevant test suites after regenerating the locks.

```bash
# from repo root
cd application/api      && uv lock --upgrade-package pytest
cd application/sdk      && uv lock --upgrade-package pytest
cd application/services && uv lock --upgrade-package pytest
```

## Recommended action plan

1. **V007 - bump pytest** to `9.0.3` across api/sdk/services uv locks, then run tests. ([#4275](https://github.com/agenta-ai/agenta/issues/4275))

### Process suggestions

- Enable Dependabot grouping. Axios alone produced 15 alerts, and grouping would make future advisory PRs easier to triage.
- Dev-only alerts (pytest, python-dotenv) inflate the dashboard. Consider Dependabot grouping or auto-merge rules for dev dependency patch bumps when CI passes.

---

## Closed (`done`)

These entries were checked against the current working tree and should no longer be applicable.

### Closed - Fix applied (dependency bumped)

#### V002 - Next.js DoS via Server Components - #529 `done`

- **Where:** [web/pnpm-lock.yaml](web/pnpm-lock.yaml).
- **Advisory:** GHSA-q4gf-8mx6-v5v3 (CVE-2026-23869). Affected: `>=13.0.0, <15.5.15`. Patched: **15.5.15** (or 16.2.3 on the 16.x line).
- **Verified current state:** Direct Next.js pins in [web/package.json](web/package.json) and [web/oss/package.json](web/oss/package.json) are `15.5.15`. [web/package.json](web/package.json) also has a `next@<15.5.15` override to `>=15.5.15`, and [web/pnpm-lock.yaml](web/pnpm-lock.yaml) no longer contains `next@15.5.14` or `next: 15.5.14`.

#### V001 - axios cluster - `web/pnpm-lock.yaml` `done`

Alerts (15): #552, #558, #628, #629, #630, #631, #632, #633, #634, #635, #636, #637, #638, #639, #640. Tracked under [#4264](https://github.com/agenta-ai/agenta/issues/4264).

Multiple advisories against the same axios install: prototype-pollution gadgets, NO_PROXY bypass / SSRF, CRLF injection, DoS variants, and null-byte injection.

**Per-advisory patched version:**

| Patched in | Advisories |
| --- | --- |
| 1.15.0 | #552, #558 |
| 1.15.1 | #628, #631, #632, #633, #634, #635, #636, #637, #638, #639, #640 |
| 1.15.2 | #629, #630 |

**Verified current state:** [web/package.json](web/package.json) overrides axios to `1.16.0`, and [web/pnpm-lock.yaml](web/pnpm-lock.yaml) resolves `axios@1.16.0`. No `axios@1.13.5` entry remains.

#### V003 - lodash `_.template` code injection - #499, #501 `done`

- **Where:** [docs/](docs/) lockfiles.
- **Advisory:** GHSA-r5fr-rjxr-66jc. Affected: `>=4.0.0, <=4.17.23`. Patched: **4.18.0**.
- **Verified current state:** [docs/package.json](docs/package.json) pins `lodash` to `^4.18.1`, [docs/pnpm-lock.yaml](docs/pnpm-lock.yaml) resolves `lodash@4.18.1`, and [docs/package-lock.json](docs/package-lock.json) has top-level `lodash@4.18.1`.

#### V004 - follow-redirects auth header leak - #547, #548 `done`

- **Where:** [docs/](docs/) lockfiles.
- **Advisory:** GHSA-r4q5-vmmm-2653. Affected: `<=1.15.11`. Patched: **1.16.0**.
- **Verified current state:** [docs/pnpm-lock.yaml](docs/pnpm-lock.yaml) and [docs/package-lock.json](docs/package-lock.json) resolve `follow-redirects@1.16.0`.

#### V005 - postcss XSS via unescaped `</style>` - #585, #587, #588 `done`

- **Where:** [web/](web/) and [docs/](docs/) lockfiles.
- **Advisory:** GHSA-qx2v-qp2m-jg93. Affected: `<8.5.10`. Patched: **8.5.10**.
- **Verified current state:** [web/pnpm-lock.yaml](web/pnpm-lock.yaml) resolves `postcss@8.5.10`; [docs/package.json](docs/package.json) pins `postcss` to `^8.5.14`; [docs/pnpm-lock.yaml](docs/pnpm-lock.yaml) and [docs/package-lock.json](docs/package-lock.json) resolve `postcss@8.5.14`.

#### V006 - uuid buffer bounds check - #642 `done`

- **Where:** [web/pnpm-lock.yaml](web/pnpm-lock.yaml).
- **Advisory:** GHSA-w5hq-g745-h8pq. Affected: `11.0.0-11.1.0`, `12.0.0`, `13.0.0`. Patched: **11.1.1** / 12.0.1 / 13.0.1.
- **Verified current state:** [web/pnpm-lock.yaml](web/pnpm-lock.yaml) resolves `uuid@11.1.1`. No `uuid@11.1.0` entry remains.

#### V008 - python-dotenv symlink-following file overwrite - #562, #563 `done`

- **Where:** [api/oss/tests/legacy/requirements.test.txt](api/oss/tests/legacy/requirements.test.txt) and [sdk/oss/tests/legacy/new_tests/requirements.test.txt](sdk/oss/tests/legacy/new_tests/requirements.test.txt).
- **Advisory:** GHSA-mf9w-mj56-hr94. Affected: `<1.2.2`. Patched: **1.2.2**.
- **Verified current state:** Both test requirement files use `python-dotenv>=1.2.2`; no `python-dotenv==1.0.0` test pin remains.

### Closed - Resolved by lockfile removal

These were resolved by removing the scanned lockfiles. The package manifests may remain, but Dependabot has no matching lockfile to scan.

#### V009 - protobufjs arbitrary code execution - #559, #560 `done`

Both example lockfiles were removed: [examples/node/observability-vercel-ai/package-lock.json](examples/node/observability-vercel-ai/package-lock.json) and [examples/node/observability-opentelemetry/pnpm-lock.yaml](examples/node/observability-opentelemetry/pnpm-lock.yaml).

#### V010 - Next.js DoS - #528, #532 `done`

Both alerts were against removed example lockfiles, including [examples/python/RAG_QA_chatbot/frontend/pnpm-lock.yaml](examples/python/RAG_QA_chatbot/frontend/pnpm-lock.yaml). The production Next.js alert #529 is closed separately as V002.

#### V011 - dompurify cluster - #512, #513, #554, #568, #571, #572 `done`

All six DOMPurify alerts were against removed [examples/python/RAG_QA_chatbot/frontend/pnpm-lock.yaml](examples/python/RAG_QA_chatbot/frontend/pnpm-lock.yaml).

#### V012 - postcss - #586 `done`

This was the RAG_QA_chatbot example lockfile only, and that lockfile has been removed.

#### V013 - uuid - #641 `done`

This was the RAG_QA_chatbot example lockfile only, and that lockfile has been removed. The production uuid alert #642 is closed separately as V006.

#### V014 - pytest poetry-side alerts - #534, #535, #536 `done`

Resolved by deleting [api/poetry.lock](api/poetry.lock), [sdk/poetry.lock](sdk/poetry.lock), and [services/poetry.lock](services/poetry.lock) as part of the uv migration. Three uv-side pytest alerts (#643, #644, #645) remain open as V007.
