# Tracing API Cleanup

## Goal

Flatten the tracing API surface to match the rest of the codebase's resource-first convention, eliminate duplicates, and reduce the public surface (drop API ingest in favor of OTLP + explicit create).

## Current state (problems)

- `/tracing/*` is the only category-grouping prefix in the API; every other domain is flat (`/variants`, `/evaluations`, `/applications`, etc.).
- `/traces/*`, `/spans/*`, and `/tracing/*` overlap heavily — same handlers, different response shapes via a `focus` flag.
- `/preview/*` re-mounts of the same routers exist with `include_in_schema=False` (migration leftovers).
- Two analytics endpoints coexist: `/tracing/spans/analytics` (legacy, fixed metrics, `OldAnalyticsResponse`) and `/tracing/analytics/query` (spec-based, current). The new one is a strict superset.
- Three ingest paths: `/otlp/v1/traces`, `/tracing/spans/ingest`, `/traces/ingest` — the latter two are wrappers around the same service method.

## Target surface

### Canonical (keep / add)

```
SPANS                                  TRACES
POST /spans/query                      POST /traces/query
POST /spans/analytics/query            POST /traces/analytics/query
POST /spans/sessions/query             POST /traces/sessions/query
POST /spans/users/query                POST /traces/users/query
GET  /spans/                           GET  /traces/
GET  /spans/{trace_id}/{span_id}       GET  /traces/{trace_id}
                                       POST /traces/                  (create)
                                       PUT  /traces/{trace_id}        (edit)
                                       DELETE /traces/{trace_id}      (delete)
```

Also kept unchanged:
- `/simple/traces/*` — simplified SDK surface (no `/simple/spans/*`; trace-only is intentional).
- `/otlp/v1/traces` — OTel ingest, the production path.

### Design decisions

**Verb suffix on read RPCs.** `query`, `analytics/query`, `sessions/query`, `users/query` use `query` as a verb suffix. Bare `/spans/query` and `/traces/query` are the primary operations on the resource; `analytics`, `sessions`, `users` are sub-views that are then queried.

**Sessions / users symmetry.** Response shape is identical on both spans and traces: `{ count, session_ids | user_ids, windowing }`. The spans-vs-traces axis only changes *what counts as a match* in the underlying filter (any span matches vs. any trace matches). Same dimension query, two natural URL surfaces.

**Analytics symmetry — implementation #1.** Single service method with `focus=SPAN|TRACE`. Both URLs route to the same code path; the focus flag selects which metric field to sum (incremental vs. cumulative). Trace-row-native aggregation can be added later without changing the API surface.

**Ingest dropped from the public API.** No `/spans/ingest`, no `/traces/ingest`. Two real ways in:
- **OTLP** (`/otlp/v1/traces`) — instrument with OTel.
- **Create** (`POST /traces/`) — explicit per-trace creation.

**GET multi-id query params.** Both repeated (`?trace_id=a&trace_id=b`) and CSV (`?trace_ids=a,b,c`) forms remain accepted. No canonicalization.

## Deprecated

Mark with `deprecated=True` in FastAPI **and** retag with `tags=["deprecated"]` so the OpenAPI spec groups them under a Deprecated section. SDK regeneration will exclude them. **No cutover** — endpoints remain functional.

- All of `/tracing/*` (entire `TracingRouter` mount)
- All of `/preview/*` mounts (`/preview/tracing/*`, `/preview/traces/*`, `/preview/spans/*`)
- `/spans/ingest`, `/traces/ingest`, `/tracing/spans/ingest`
- `/tracing/spans/analytics` (the `legacy_analytics` handler)

## Files to edit

1. **[application/api/oss/src/apis/fastapi/tracing/router.py](application/api/oss/src/apis/fastapi/tracing/router.py)**
   - `SpansRouter` (~line 695): add `analytics/query`, `sessions/query`, `users/query` routes wired to the existing `TracingService.analytics`, `TracingService.sessions`, `TracingService.users` with `focus=SPAN`.
   - `TracesRouter` (~line 923): add `analytics/query`, `sessions/query`, `users/query` routes with `focus=TRACE`. Confirm trace CRUD (POST/, GET/{id}, PUT/{id}, DELETE/{id}) is present and canonical.
   - Mark legacy ingest routes (`/spans/ingest`, `/traces/ingest`) with `deprecated=True` and `tags=["deprecated"]` at the route level.
   - Mark `fetch_legacy_analytics` route (`/tracing/spans/analytics`) the same way.

2. **[application/api/entrypoints/routers.py](application/api/entrypoints/routers.py)** (~lines 683–768)
   - On the `/tracing/*` mount and all `/preview/*` mounts: pass `deprecated=True` and `tags=["deprecated"]` to `include_router`.

3. **OpenAPI spec regeneration** — auto-generated; verify the Deprecated tag groups all expected endpoints and the SDK regeneration excludes them.

## Open follow-ups (post-cleanup)

- Decide whether to eventually implement trace-row-native analytics (vs. current focus-flag reuse of span-row aggregation).
- Decide on a removal date for the deprecated endpoints once SDK / client migrations are tracked.
