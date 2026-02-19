# Code Review — Gateway Tools (`feat/add-gateway-tools`)

> Reviewer guide: findings are grouped by dimension. Each item carries a severity tag:
> **[BLOCKER]** must be resolved before merge · **[MAJOR]** strong recommendation · **[MINOR]** improvement · **[NIT]** style/polish

---

## 1. Functional Correctness

### 1.1 `get_integration` performs a full scan — O(N) on every call

**File:** `api/oss/src/core/tools/service.py:89-97`

```python
integrations, _, _ = await adapter.list_integrations(limit=1000)
for i in integrations:
    if i.key == integration_key:
        target = i
```

`list_integrations(limit=1000)` issues a full Composio API call on every single `GET /catalog/.../integrations/{key}` request. The Redis cache in the router layer only caches the list response for the current page params, so a direct `get_integration` path always misses.

**[MAJOR]** Add a dedicated `get_integration(integration_key)` call to the Composio API (or cache the full catalog client-side in the adapter at startup) instead of fetching 1000 records and iterating in Python.

---

### 1.2 `callback_connection` swallows all exceptions silently

**File:** `api/oss/src/apis/fastapi/tools/router.py:868`

```python
try:
    conn = await self.tools_service.activate_connection_by_provider_connection_id(...)
    ...
except Exception:
    pass
```

A bare `except Exception: pass` means a DB failure (e.g., network split, schema mismatch) will silently result in a success card being shown to the user while the connection is never actually activated in the database.

**[BLOCKER]** At minimum, log the exception. Better: distinguish recoverable decoration errors (e.g., logo fetch failed) from critical activation failures (DB write failed) and return a failure card for the latter.

---

### 1.3 `call_tool` returns `200 OK` on execution errors

**File:** `api/oss/src/apis/fastapi/tools/router.py:1014-1028`

```python
except Exception as e:
    log.error(f"Tool execution failed: {e}")
    result = ToolResult(... status=Status(code="STATUS_CODE_ERROR") ...)
    return ToolCallResponse(call=result)
```

An exception during tool execution returns `HTTP 200` with an error body. Clients that only check the HTTP status will silently treat failures as successes. This is intentional if the design wants always-200 for tool results (to pass back to the LLM), but the contract should be documented explicitly.

**[MINOR]** If the intent is OpenAI-compatible always-succeed semantics (let the LLM see the error), add a comment and document the behaviour in the API reference. Otherwise, consider `HTTP 502` for hard adapter failures.

---

### 1.4 Connection query does not filter by `is_active`

**File:** `api/oss/src/core/tools/service.py:138-151`

`query_connections` delegates straight to the DAO with no `is_active` filter. The `call_tool` handler checks `connection.is_active` after fetching all connections, but a project with many soft-deleted connections will still materialise all of them from the DB.

**[MINOR]** The DAO query should default to `WHERE flags->>'is_active' = 'true'` (or equivalent) unless the caller explicitly requests archived connections.

---

### 1.5 `refresh_connection` contains provider-specific branching in the service

**File:** `api/oss/src/core/tools/service.py:347-365`

```python
if conn.provider_key.value == "composio":
    result = await adapter.initiate_connection(...)
else:
    result = await adapter.refresh_connection(...)
```

The service layer has a hardcoded `"composio"` branch. The Adapter pattern exists precisely to push provider-specific logic into the adapter.

**[MAJOR]** Move this branching into `ComposioAdapter.refresh_connection()` so the service calls a single `adapter.refresh_connection()` regardless of provider.

---

### 1.6 Agenta provider skeleton contains all empty files

**Files:** `api/oss/src/core/tools/providers/agenta/`

All six files in this package are completely empty (0 bytes). They add noise to the directory listing and import graph without contributing any value yet.

**[MINOR]** Either add at minimum a module-level docstring / `NotImplementedError` stub, or defer these files to the PR that actually implements the Agenta provider.

---

## 2. Security

### 2.1 OAuth callback is unauthenticated and tenant-unscoped

**File:** `api/oss/src/apis/fastapi/tools/router.py:815-870`

The `/connections/callback` endpoint has **no authentication guard** and **no `@intercept_exceptions()`** decorator. It activates a connection based solely on a `connected_account_id` query parameter supplied in the redirect URL.

```python
async def callback_connection(
    self,
    request: Request,
    *,
    connected_account_id: Optional[str] = Query(default=None),
    ...
```

An attacker who knows (or guesses) a valid Composio `connected_account_id` can trigger `activate_connection_by_provider_connection_id` for any project, marking an arbitrary connection as valid without authenticating as the project owner.

**[BLOCKER]** Bind the OAuth state to a short-lived, signed `state` parameter that encodes `project_id` + `user_id` + nonce (standard OAuth `state` flow). Validate the signature on callback before activating any connection. Composio's V3 API supports passing a `state` value through the redirect URL.

---

### 2.2 API key stored in environment variable — not validated at startup

**File:** `api/oss/src/utils/env.py` + `api/entrypoints/routers.py`

`COMPOSIO_API_KEY` is read from env and passed directly to `ComposioAdapter`. If the key is missing or malformed, the router mounts successfully but every catalog call will fail with a 401/403 from Composio. There is no startup validation.

**[MINOR]** Add an early check: if `COMPOSIO_ENABLED=true` and `COMPOSIO_API_KEY` is blank/missing, log a clear error and either raise at startup or skip mounting the adapter so the error is surfaced immediately rather than on the first request.

---

### 2.3 `_oauth_card` renders user-controlled data into an HTML string without escaping

**File:** `api/oss/src/apis/fastapi/tools/router.py:1036+`

```python
f'<img src="{integration_logo}" alt="{int_alt}" class="logo" />'
```

`integration_logo` and `integration_label` come from the Composio API response. If Composio's response is ever compromised or tampered with (supply-chain scenario), a crafted `logo` URL or label value containing `"` could escape attribute values and inject HTML.

**[MINOR]** HTML-escape all values interpolated into the HTML card. Python's `html.escape()` is sufficient.

---

### 2.4 Tool slug is parsed from the LLM response without sanitisation

**File:** `api/oss/src/apis/fastapi/tools/router.py:905`

```python
slug_parts = body.data.function.name.replace("__", ".").split(".")
```

The tool name is returned verbatim by the LLM and is used to construct a provider key, integration key, and action key that are sent to the Composio API. While the DAO lookup enforces project scope, the adapter HTTP calls could receive attacker-controlled `integration_key` / `action_key` values (path traversal or injection).

**[MAJOR]** Validate each slug segment against an allowlist (alphanumeric + underscore + hyphen only) before using them as path components in outgoing HTTP requests.

---

### 2.5 `provider_connection_id` appears in log output

**File:** `api/oss/src/apis/fastapi/tools/router.py:843`

```python
log.info("OAuth callback received - connected_account_id: %s, ...", connected_account_id, ...)
```

`connected_account_id` is a sensitive credential handle. Logging it at INFO level means it will be written to application logs (and potentially log aggregation services) in plaintext.

**[MINOR]** Log a truncated/hashed version or omit it entirely. Use DEBUG level if it's needed for troubleshooting, with a note that debug logs should never go to production aggregators.

---

## 3. Performance

### 3.1 New `httpx.AsyncClient()` per request — no connection pooling

**File:** `api/oss/src/core/tools/providers/composio/adapter.py:46-59`

```python
async def _get(self, path, *, params=None):
    async with httpx.AsyncClient() as client:
        resp = await client.get(...)
```

A new TCP connection (and TLS handshake) is established for every single call to the Composio API. Under moderate load this adds 50–200 ms of overhead per request and creates thundering-herd conditions on catalog page loads.

**[MAJOR]** Create one `httpx.AsyncClient` per adapter instance (or a shared connection pool), close it on adapter teardown (via lifespan). This is the idiomatic httpx pattern.

---

### 3.2 `list_providers` fanout: one DB + one Composio call per provider per catalog request

**File:** `api/oss/src/apis/fastapi/tools/router.py:211-226`

When `full_catalog=true` (the default), `list_providers` calls `list_integrations` for every provider. `list_integrations` itself has its own cache. But the cache is keyed per `project_id`, so a deployment with many projects will repeatedly warm identical Composio data independently.

**[MINOR]** The Composio catalog is global (not per-project). Cache catalog responses at the **application level** (not per-project namespace) for maximum reuse.

---

### 3.3 Redis cache miss path on `get_integration` causes unbounded work

See §1.1 — a cache miss on `get_integration` loads 1000 records from Composio. Since this path is not separately cached with a simple `integration_key` key, a steady stream of integration detail requests will hammer the Composio API.

**[MAJOR]** Cache individual `(provider_key, integration_key)` pairs in the adapter or router, not just list results.

---

### 3.4 Synchronous `json.loads` in the hot tool-call path

**File:** `api/oss/src/apis/fastapi/tools/router.py:977-983`

```python
if isinstance(arguments, str):
    try:
        arguments = json.loads(arguments)
    except Exception:
        arguments = {}
```

Silently swallowing a JSON parse error (returning `{}`) hides malformed LLM output. The tool will execute with empty arguments and likely produce a confusing error downstream.

**[MINOR]** Log a warning when `json.loads` fails so the malformed LLM output is observable. An empty `{}` is acceptable as a fallback, but the failure should be surfaced.

---

## 4. Architecture & Design

### 4.1 Domain exceptions defined in `core/` are caught in `router.py` via inline `if not X → return JSONResponse`

**Files:** `api/oss/src/apis/fastapi/tools/router.py` (multiple call_tool guards)

The project standard (per AGENTS.md) is to define domain exceptions in `core/`, raise them from the service, and catch them at the router boundary — either via a decorator or a `try/except` block in the route handler. The `call_tool` handler mixes this with inline `JSONResponse` returns for every precondition check.

```python
if not connection:
    return JSONResponse(status_code=404, content={"detail": "..."})
if not connection.is_active:
    return JSONResponse(status_code=400, content={"detail": "..."})
```

**[MINOR]** Move these guards into the service (raise `ConnectionNotFoundError`, `ConnectionInactiveError`) and catch them at the router boundary consistently. The exceptions are already defined in `core/tools/exceptions.py`.

---

### 4.2 Router `list_integrations` is called recursively from other router methods

**File:** `api/oss/src/apis/fastapi/tools/router.py:215, 289`

```python
integrations_response = await self.list_integrations(
    request=request,
    provider_key=provider.key,
    ...
)
```

A router handler calling another router handler couples them by internal API and re-runs the EE permission check, cache check, and logging for what is effectively an internal composition. This also risks double-logging and double-cache-write.

**[MINOR]** Extract a private `_fetch_integrations(...)` helper on the router (or push the composition logic to the service) and call that from both `list_providers` and `list_integrations`.

---

### 4.3 `ToolConnectionDBE.kind` and `provider_key` are redundant

**File:** `api/oss/src/dbs/postgres/tools/dbes.py:64-76`

```python
kind = Column(Enum(ToolProviderKind), nullable=False)
provider_key = Column(String, nullable=False)
```

Both columns store the same information (`kind` is the enum, `provider_key` is its string value). The unique constraint and index only use `provider_key`, but mapping code must keep both in sync.

**[MINOR]** Choose one (prefer the `Enum` column for type safety + constraint enforcement at the DB level) and derive the other via a `@property` if needed.

---

### 4.4 `activate_connection_by_provider_connection_id` bypasses `project_id` scope

**File:** `api/oss/src/core/tools/service.py:163-171`

```python
async def activate_connection_by_provider_connection_id(
    self,
    *,
    provider_connection_id: str,
) -> Optional[ToolConnection]:
```

This service method (called from the unauthenticated OAuth callback) updates a connection identified only by the provider-side ID, with no `project_id` guard. Even if Composio IDs are unguessable, the absence of a scope check is an architectural anti-pattern.

**[MAJOR]** At minimum, document explicitly why the scope check is intentionally omitted here (the `state` param fix in §2.1 would allow re-introducing `project_id`). Pair with the §2.1 fix.

---

### 4.5 `providers/` package boundary is ambiguous

**Files:** `api/oss/src/core/tools/providers/interfaces.py`, `providers/service.py`, `providers/types.py`, `providers/exceptions.py`

All four files in `providers/` root are empty. Only `providers/composio/` contains implementation. This creates an unclear abstraction boundary — it's not obvious whether `providers/interfaces.py` is meant to differ from `core/tools/interfaces.py`.

**[MINOR]** Either delete the empty `providers/` root files and consolidate interfaces into `core/tools/interfaces.py`, or populate them with the intended separation and add docstrings explaining the layering.

---

### 4.6 Cron scripts added without corresponding documentation or scheduler wiring

**Files:** `api/oss/src/crons/tools.sh`, `api/oss/src/crons/tools.txt`

Two cron-related files are added but there is no documentation of what they do, when they run, or how they are wired into the deployment. The Dockerfile shows `cron` is installed, but the connection to `tools.sh` is not clear.

**[MINOR]** Add a short README in `crons/` or inline comments in the shell script explaining the job's purpose (assumed: poll Composio to sync connection statuses), schedule, and failure behaviour.

---

## 5. Documentation

### 5.1 Extensive design docs but no inline docstrings on public service methods

The `docs/designs/gateway-tools/` directory is thorough. However, the service (`service.py`) and DAO (`dao.py`) have minimal or no docstrings on public methods.

**[MINOR]** Add one-line docstrings to `ToolsService` public methods (especially `execute_tool`, `refresh_connection`, `activate_connection_by_provider_connection_id`) so the intent is clear to future contributors without reading the full design docs.

---

### 5.2 API reference doc and implementation diverge on slug format

**File:** `docs/designs/gateway-tools/api-reference.md` vs `router.py:905-918`

The API reference describes the slug as `tools.{provider}.{integration}.{action}`, but the router also supports a 5th segment (`{connection}`) and treats a missing connection slug as a hard error. The docs do not mention the 5th segment or that it is required.

**[MINOR]** Update the API reference to document the full 5-part slug format: `tools.{provider}.{integration}.{action}.{connection}`.

---

### 5.3 Environment variable `COMPOSIO_ENABLED` is not documented in `README` or compose files comment

`docker-compose.dev.yml` adds the variable but only via an inline comment. No top-level documentation lists all required environment variables for enabling the gateway tools feature.

**[NIT]** Add a short block in the main deployment docs (or `docs/designs/gateway-tools/TOOLS_IMPLEMENTATION.md`) listing all env vars, their defaults, and how to obtain a Composio API key.

---

## 6. Test Coverage

### 6.1 No automated tests for the new domain

The PR adds manual `.http` test collections, which is helpful for exploratory testing, but there are no unit or integration tests for:

- `ToolsService` (service logic, connection lifecycle)
- `ToolsDAO` (database reads/writes, constraint handling)
- `ComposioAdapter` (HTTP client, error mapping)
- Router input validation (slug parsing, permission enforcement)

**[MAJOR]** Given the scope (11 new endpoints, a new DB table, an external HTTP client, and OAuth flow), automated tests are needed before this lands on `main`. Even a small set of unit tests mocking the adapter and DAO would catch the issues in §1.2–1.4.

---

### 6.2 No tests for the OAuth callback flow

The callback handler (`callback_connection`) is the most security-sensitive code path. It is also stateful (DB update) and side-effectful (HTML rendered). It has no tests.

**[BLOCKER]** Add at minimum a test that:
1. Verifies a valid `connected_account_id` activates the correct connection.
2. Verifies a missing / invalid `connected_account_id` returns a failure card.
3. Verifies a DB failure returns a failure card (not a success card — see §1.2).

---

## Summary Table

| # | Dimension | Severity | Short description |
|---|-----------|----------|-------------------|
| 1.1 | Functional | MAJOR | `get_integration` loads 1000 records per call |
| 1.2 | Functional | BLOCKER | Callback swallows DB exceptions, shows false success |
| 1.3 | Functional | MINOR | `call_tool` returns HTTP 200 on adapter errors |
| 1.4 | Functional | MINOR | `query_connections` returns soft-deleted connections |
| 1.5 | Functional | MAJOR | Provider-specific branch in service layer |
| 1.6 | Functional | MINOR | Agenta provider skeleton is all empty files |
| 2.1 | Security | BLOCKER | Unauthenticated OAuth callback — CSRF / account takeover risk |
| 2.2 | Security | MINOR | No startup validation of `COMPOSIO_API_KEY` |
| 2.3 | Security | MINOR | `_oauth_card` renders unescaped Composio data into HTML |
| 2.4 | Security | MAJOR | Tool slugs from LLM not validated before use as API path components |
| 2.5 | Security | MINOR | `connected_account_id` logged at INFO level |
| 3.1 | Performance | MAJOR | New `httpx.AsyncClient` per request — no connection pooling |
| 3.2 | Performance | MINOR | Catalog cache keyed per-project instead of application-level |
| 3.3 | Performance | MAJOR | Cache miss on `get_integration` fetches 1000 records |
| 3.4 | Performance | MINOR | Silent `json.loads` failure returns empty args with no log |
| 4.1 | Architecture | MINOR | Inline `JSONResponse` instead of domain exception pattern |
| 4.2 | Architecture | MINOR | Router handler calls sibling router handler recursively |
| 4.3 | Architecture | MINOR | `kind` and `provider_key` columns redundant in DBE |
| 4.4 | Architecture | MAJOR | `activate_connection_by_provider_id` bypasses project scope |
| 4.5 | Architecture | MINOR | Empty `providers/` root package boundary is unclear |
| 4.6 | Architecture | MINOR | Cron scripts undocumented and unconnected to scheduler |
| 5.1 | Docs | MINOR | No inline docstrings on public service/DAO methods |
| 5.2 | Docs | MINOR | API reference misses mandatory 5th slug segment |
| 5.3 | Docs | NIT | Env vars not documented outside compose comment |
| 6.1 | Tests | MAJOR | No automated tests for new domain |
| 6.2 | Tests | BLOCKER | No tests for OAuth callback (security-critical path) |

**Blockers (must fix):** 1.2 · 2.1 · 6.2
**Majors (strong recommendation):** 1.1 · 1.5 · 2.4 · 3.1 · 3.3 · 4.4 · 6.1
