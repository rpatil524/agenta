# Dependabot Vulnerability Triage

Snapshot of Dependabot alerts as of 2026-05-06, split into **Open** (still needs action) and **Closed / `fixed`** (resolved by removing example lockfiles — should auto-close on next Dependabot scan).

## Summary by location

| Lockfile | Alerts | Status |
| --- | --- | --- |
| [web/pnpm-lock.yaml](web/pnpm-lock.yaml) | 18 (axios cluster, next, postcss, uuid) | open |
| [docs/pnpm-lock.yaml](docs/pnpm-lock.yaml) + [docs/package-lock.json](docs/package-lock.json) | 6 (lodash, follow-redirects, postcss) | open |
| [api/](api/), [sdk/](sdk/), [services/](services/) lockfiles | 6 (pytest, python-dotenv) | open |
| ~~examples/python/RAG_QA_chatbot/frontend/pnpm-lock.yaml~~ | ~~9~~ | **`fixed`** |
| ~~examples/node/observability-vercel-ai/package-lock.json~~ | ~~1~~ | **`fixed`** |
| ~~examples/node/observability-opentelemetry/pnpm-lock.yaml~~ | ~~1~~ | **`fixed`** |

---

## Open

Alerts still requiring code/dependency changes.

### Open — High

#### V001 — axios cluster — `web/pnpm-lock.yaml` ✅ done

Alerts (15): #552, #558, #628, #629, #630, #631, #632, #633, #634, #635, #636, #637, #638, #639, #640. Tracked under [#4264](https://github.com/agenta-ai/agenta/issues/4264).

Multiple advisories against the same axios install: prototype-pollution gadgets (response tampering, header injection, credential injection, cloud-metadata exfiltration), NO_PROXY bypass / SSRF, CRLF injection, DoS variants, and null-byte injection.

**Per-advisory patched version (verified against github.com/advisories):**

| Patched in | Advisories |
| --- | --- |
| 1.15.0 | #552, #558 |
| 1.15.1 | #628, #631, #632, #633, #634, #635, #636, #637, #638, #639, #640 |
| 1.15.2 | #629, #630 |

Pinning to **1.16.0** covers all 15.

**Root cause:** A `pnpm.overrides` block in [web/package.json](web/package.json) forced axios to `1.13.5` despite workspace pins at `1.16.0`.

**Fix applied — bump the override and reinstall:**

```bash
# from repo root
sed -i '' 's/"axios": "1.13.5"/"axios": "1.16.0"/' application/web/package.json
cd application/web && pnpm install
```

Lockfile now resolves `axios@1.16.0`. Smoke-test API calls and the XSRF flow before merging.

#### V002 — Next.js DoS via Server Components — #529

- **Where:** Direct dep in [web/oss/package.json](web/oss/package.json). Tracked in [#4132](https://github.com/agenta-ai/agenta/issues/4132).
- **Impact:** Crafted RSC payload can hang the server; relevant for the production web app.
- **Fix:** Bump `next` to the patched minor. Verify build.

#### V003 — lodash — `_.template` code injection — #499, #501

- **Where:** [docs/](docs/) lockfiles only.
- **Impact:** Docs site doesn't appear to use `_.template` with user input, so exploitability is low — but bumping is cheap.
- **Fix:** Update `lodash` to the patched 4.17.x line. Already covered by a pnpm override in [web/package.json](web/package.json) (`"lodash@<4.17.23": ">=4.17.23"`); replicate in [docs/](docs/) or bump directly.

```bash
# from repo root — pnpm side
cd application/docs && pnpm up lodash@latest -r && pnpm install
# npm side
cd application/docs && npm update lodash --save
```

### Open — Moderate

#### V004 — follow-redirects — auth header leak on cross-domain redirect — #547, #548

- **Where:** [docs/](docs/) only.
- **Fix:** Bump to >= 1.15.6.

```bash
# from repo root
cd application/docs && pnpm up follow-redirects@latest -r && pnpm install
cd application/docs && npm update follow-redirects --save
```

#### V005 — postcss — XSS via unescaped `</style>` — #585, #587, #588

- **Where:** [web/](web/), [docs/](docs/).
- **Impact:** Only matters if PostCSS output is rendered untrusted; for build-time CSS this is theoretical. Still worth bumping.
- **Fix:** Bump `postcss` to the patched 8.4.x+ line. Cleanest path: add a pnpm override matching the existing pattern in [web/package.json](web/package.json).

```bash
# from repo root — bump in web/ via pnpm override (recommended; matches existing pattern)
# edit application/web/package.json pnpm.overrides to add:  "postcss@<8.4.31": ">=8.4.31"
cd application/web && pnpm install

# bump in docs/
cd application/docs && pnpm up postcss@latest -r && pnpm install
cd application/docs && npm update postcss --save
```

#### V006 — uuid — buffer bounds check — #642

- **Where:** [web/pnpm-lock.yaml](web/pnpm-lock.yaml). Tracked in [#4276](https://github.com/agenta-ai/agenta/issues/4276).
- **Impact:** Affects `v3/v5/v6` with caller-provided buffer — we don't appear to use those forms. Low real risk.
- **Fix:** Bump `uuid` to patched release.

```bash
# from repo root
cd application/web && pnpm up uuid@latest -r && pnpm install
```

#### V007 — pytest — tmpdir handling — #534, #535, #536, #643, #644, #645

- **Where:** [api/](api/), [sdk/](sdk/), [services/](services/) — both `poetry.lock` and `uv.lock` carry alerts (incomplete migration). Tracked in [#4275](https://github.com/agenta-ai/agenta/issues/4275).
- **Impact:** Dev-only dependency, local-only attack surface. Low risk.
- **Fix:** Bump `pytest` in dev-dependencies. Also: pick poetry XOR uv per project and delete the other lockfile to stop duplicate alerts.

```bash
# from repo root — uv side (forward path)
cd application/api      && uv lock --upgrade-package pytest
cd application/sdk      && uv lock --upgrade-package pytest
cd application/services && uv lock --upgrade-package pytest

# poetry side (delete after migrating off poetry)
cd application/api      && poetry update pytest
cd application/sdk      && poetry update pytest
cd application/services && poetry update pytest

# dedup: once uv is the source of truth, remove poetry.lock
rm application/api/poetry.lock application/sdk/poetry.lock application/services/poetry.lock
```

#### V008 — python-dotenv — symlink-following file overwrite — #562, #563

- **Where:** test requirements files for sdk and api. Tracked in [#4204](https://github.com/agenta-ai/agenta/issues/4204).
- **Impact:** Dev-only, requires attacker-controlled symlink in test workdir. Negligible.
- **Fix:** Bump pin in the `requirements.test.txt` files (advisory: >= 1.1.1).

```bash
# from repo root — pin bump (replace with current safe version per advisory)
sed -i '' 's/^python-dotenv==.*/python-dotenv>=1.1.1/' \
  application/api/oss/tests/legacy/requirements.test.txt \
  application/sdk/oss/tests/legacy/new_tests/requirements.test.txt
```

## Recommended action plan (open items)

1. ~~**V001 — axios bump in [web/](web/)** — clears 15 alerts at once. ([#4264](https://github.com/agenta-ai/agenta/issues/4264))~~ ✅ done — override bumped 1.13.5 → 1.16.0; lockfile resolves cleanly.
2. **V002 — next.js bump** in [web/oss/package.json](web/oss/package.json). ([#4132](https://github.com/agenta-ai/agenta/issues/4132))
3. **V005 + V006 — postcss + uuid bump** in [web/](web/) — usually a clean transitive update.
4. **V003 + V004 — lodash + follow-redirects bump** in [docs/](docs/) — batch into one docs-deps PR.
5. **V007 — pytest bump + lockfile dedup** ([#4275](https://github.com/agenta-ai/agenta/issues/4275)) — pick poetry XOR uv per project.
6. **V008 — python-dotenv bump** in `requirements.test.txt` files. ([#4204](https://github.com/agenta-ai/agenta/issues/4204))

### Process suggestions

- Enable Dependabot grouping (axios alone produced 12 alerts). A `dependabot.yml` group config means future advisories land as one PR.
- Dev-only alerts (pytest, python-dotenv) inflate the dashboard. Consider Dependabot's `vulnerability-alerts` filter to deprioritize `dev` scope, or auto-merge dev-dep patches via CI.

---

## Closed (`fixed`)

Resolved by removing the example app lockfiles. The `package.json` files remain, but with no lockfile Dependabot has nothing to scan. These should auto-close on the next scan.

### Closed — Critical

#### V009 — protobufjs — Arbitrary code execution — #559, #560 `fixed`

Both example lockfiles ([examples/node/observability-vercel-ai/package-lock.json](examples/node/observability-vercel-ai/package-lock.json), [examples/node/observability-opentelemetry/pnpm-lock.yaml](examples/node/observability-opentelemetry/pnpm-lock.yaml)) removed.

### Closed — High

#### V010 — Next.js DoS — #528, #532 `fixed`

Both alerts were against example lockfiles (RAG_QA_chatbot frontend and a transitive case). Note: #529 (production [web/oss/](web/oss/)) is still **open** — see above.

### Closed — Moderate

#### V011 — dompurify cluster — #512, #513, #554, #568, #571, #572 `fixed`

All six DOMPurify alerts were against [examples/python/RAG_QA_chatbot/frontend/pnpm-lock.yaml](examples/python/RAG_QA_chatbot/frontend/pnpm-lock.yaml).

#### V012 — postcss — #586 `fixed`

RAG_QA_chatbot example only. Production postcss alerts (#585, #587, #588) are still **open**.

#### V013 — uuid — #641 `fixed`

RAG_QA_chatbot example only. Production uuid alert (#642) is still **open**.
