# RFC: Testset Creation from Annotation Queue — Technical Design

## Status

Draft.

## Summary

This RFC describes the frontend-only implementation of testset export from annotation queues. No new backend API endpoints are required; all export operations use the existing `patchRevision` and `createTestset` API functions. Large exports run as frontend background jobs that keep progress in Jotai state while the user can continue annotating. The changes are concentrated in two packages:

- `web/packages/agenta-annotation` — new controller actions and state atoms
- `web/packages/agenta-annotation-ui` — updates to three existing components; `EntityCommitModal` is reused as-is for the modal shell

---

## Architecture Overview

```
User action (button click)
        │
        ▼
openAddToTestsetModal({ scope, scenarioIds? })   ← new controller action
  sets: addToTestsetModalOpenAtom
        addToTestsetScopeAtom
        addToTestsetScenarioIdsAtom
        pendingTestsetSelectionAtom ← seeded from defaultTargetTestsetId
        │
        ▼
EntityCommitModal (reused, @agenta/entity-ui)
  ├── commitModes: ["existing", "new"]
  ├── renderModeContent → EntityPicker (adapter="testset")
  │     onSelect → setPendingTestsetSelection action
  ├── createEntityFields (new testset name/slug, "new" mode only)
  └── onSubmit → reads pendingTestsetSelectionAtom
        │
        ▼ (on confirm)
addScenariosToTestset({ scenarioIds, commitMessage, ... })  ← new action
  reads: pendingTestsetSelectionAtom for targetTestsetId
        │
        ├─ trace queue path ─────────────────────────────────────────────────┐
        │   buildTraceTestsetRows()                                          │
        │     → fetch trace inputs/outputs (traceInputsAtomFamily, etc.)     │
        │     → fetch annotations for each scenario                          │
        │     → construct row objects                                        │
        │   patchRevision() / createTestset()                                │
        │                                                                    │
        └─ testcase queue path ──────────────────────────────────────────────┘
            buildTestcaseExportRows()
              → patchRevision(existing target) / createTestset(new target)
        │
        ▼
  startAddToTestsetExportJob()
        │
        ├─ updates addToTestsetExportJobAtom with status/progress
        ├─ allows modal to close so the user can keep annotating
        └─ on success: set(lastUsedTestsetByProjectAtom[projectId], targetTestsetId)
```

---

## Package: `agenta-annotation`

### File: `src/state/testsetSync.ts` — additions

Add two new builder functions alongside the existing ones:

#### `buildTraceTestsetRows`
```typescript
interface TraceTestsetRowBuilderParams {
  scenarioIds: string[]
  // traceInputsAtomFamily returns Record<string, unknown> — one entry per input key.
  // Each key becomes its own testset column.
  traceInputsByScenario: Map<string, Record<string, unknown>>
  // traceOutputsAtomFamily returns `unknown` (string, object, array, etc.).
  // Always mapped to a single column regardless of shape; column name is resolved by the caller.
  traceOutputsByScenario: Map<string, unknown>
  // One entry per evaluator key with submitted annotation output fields.
  annotationsByScenario: Map<string, Record<string, Record<string, unknown>>>  // { [evaluatorKey]: { [fieldKey]: value } }
  // Column name for the output value. Resolved by addScenariosToTestset before calling this function:
  // - new testset → "outputs"
  // - existing testset → first match from ["correct_answer", "output", "outputs", "answer"], fallback "output"
  outputColumnName: string
}

interface TraceTestsetRow {
  scenarioId: string
  // Resulting column shape: { ...inputKeys, [outputColumnName]: <any>, "evaluator.field": <value>, ... }
  data: Record<string, unknown>
}

export function buildTraceTestsetRows(params: TraceTestsetRowBuilderParams): TraceTestsetRow[]
```

Logic:
1. For each `scenarioId` in `params.scenarioIds`:
   - **Input columns** — spread the `Record<string, unknown>` from `traceInputsByScenario` directly into `data`. Each key becomes its own column (e.g., `question`, `context`, `prompt`). This matches what `traceInputsAtomFamily` returns via `extractInputs()` → `agData.inputs`. Input keys that don't exist in the target testset's column schema are added as new columns — no filtering is applied.
   - **Output column** — add a single key named `outputColumnName` whose value is the raw `unknown` from `traceOutputsByScenario`. The value is never split or recursed into; it maps to exactly one column regardless of its type (string, object, chat message, etc.). This matches `extractOutputs()` which deliberately treats `agData.outputs` as a leaf.
   - **Annotation columns** — for each evaluator key and submitted output field in `annotationsByScenario`, add one flattened column named `${evaluatorKey}.${fieldKey}`. Skip evaluators with no submitted output fields.
2. Return the list of `TraceTestsetRow` objects.

#### `buildTestcaseExportRows`
```typescript
interface TestcaseExportRowBuilderParams {
  scenarioIds: string[]
  testcasesById: Map<string, Testcase>
  annotationsByTestcaseId: Map<string, Annotation[]>
  evaluators: TestsetSyncEvaluator[]
  queueId: string
}

export function buildTestcaseExportRows(params: TestcaseExportRowBuilderParams): TestsetSyncRow[]
```

Logic: Same annotation-output flattening as the existing sync preview, but the rows are always emitted for one explicit user-selected target. Source testset IDs are ignored for routing. Produces rows suitable for `patchRevision` `rows.add` operations or `createTestset({ testcases })`.

---

### File: `src/state/controllers/annotationSessionController.ts` — additions

#### New atoms

```typescript
// Persisted across page loads, scoped per project
const lastUsedTestsetByProjectAtom = atomWithStorage<Record<string, string | null>>(
  "agenta:annotation:last-testset-by-project",
  {},
)

const lastUsedTestsetIdAtom = atom(
  (get) => {
    const projectId = get(projectIdAtom)
    if (!projectId) return null
    return get(lastUsedTestsetByProjectAtom)[projectId] ?? null
  },
  (get, set, testsetId: string | null) => {
    const projectId = get(projectIdAtom)
    if (!projectId) return
    const byProject = get(lastUsedTestsetByProjectAtom)
    set(lastUsedTestsetByProjectAtom, {...byProject, [projectId]: testsetId})
  },
)

// Transient — modal open/close state
const addToTestsetModalOpenAtom = atom<boolean>(false)

// Which scenarios are in scope for the pending export.
// "all"      — All annotations tab, no row selection
// "selected" — All annotations tab, specific rows checked
// "single"   — Annotate tab (one scenario)
// "complete" — Done-with-queue screen (all scenarios; distinct from "all" for commit message default)
type AddToTestsetScope = "single" | "selected" | "all" | "complete"
const addToTestsetScopeAtom = atom<AddToTestsetScope>("all")
const addToTestsetScenarioIdsAtom = atom<string[]>([])

// The testset currently selected inside the open modal.
// Seeded from defaultTargetTestsetId when modal opens; updated by EntityPicker onSelect.
// Lives here — NOT in component state — so it survives re-renders without data loss.
const pendingTestsetSelectionAtom = atom<string | null>(null)

// Tracks which rows the user has checked in ScenarioListView.
// Cleared on successful export; preserved on failure so the user can retry without re-selecting.
const selectedScenarioIdsAtom = atom<string[]>([])

type AddToTestsetExportJob = {
  id: string
  status: "idle" | "preparing" | "committing" | "success" | "error"
  total: number
  processed: number
  targetTestsetId?: string
  targetTestsetName?: string
  error?: string
}

const addToTestsetExportJobAtom = atom<AddToTestsetExportJob>({
  id: "",
  status: "idle",
  total: 0,
  processed: 0,
})
```

#### New selectors (exposed on `annotationSessionController.selectors`)

| Selector | Returns | Description |
|----------|---------|-------------|
| `defaultTargetTestsetId()` | `string \| null` | Heuristic default: last used testset if set; otherwise null |
| `lastUsedTestsetId()` | `string \| null` | Persisted last-used testset ID |
| `pendingTestsetSelection()` | `string \| null` | The testset currently selected in the open modal |
| `addToTestsetExportJob()` | `AddToTestsetExportJob` | Current background export progress and terminal status |
| `defaultCommitMessage()` | `string` | Entry-point-aware default commit message: scope="single" → `"Added scenario from {queueName}"`; scope="all"/"selected" → `"{queueName}: annotated {N} scenarios"`; scope="complete" → `"{queueName}: completed annotation queue"` |
| `isAddToTestsetModalOpen()` | `boolean` | Whether the commit modal is open |
| `addToTestsetScope()` | `AddToTestsetScope` | Current export scope |
| `addToTestsetScenarioIds()` | `string[]` | Scenario IDs for "single" / "selected" scope; **empty for "all" and "complete"** — use `scenarioIds()` for total count |
| `scenarioIds()` | `string[]` | All scenario IDs in the session (existing selector, reused for "all" / "complete" scope count) |
| `canAddToTestset()` | `boolean` | True when `scenarioIds().length > 0` for trace queues; at least one completed for testcase queues |

#### New actions (exposed on `annotationSessionController.actions`)

**`openAddToTestsetModal`**
```typescript
openAddToTestsetModal: atom(null, (get, set, payload: {
  scope: AddToTestsetScope,
  scenarioIds?: string[],   // required when scope === "single" or "selected"
}) => {
  set(addToTestsetScopeAtom, payload.scope)
  set(addToTestsetScenarioIdsAtom, payload.scenarioIds ?? [])
  // Seed the pending selection from the heuristic default so the picker
  // opens with the right testset pre-selected without needing component state
  set(pendingTestsetSelectionAtom, get(defaultTargetTestsetIdAtom))
  set(addToTestsetModalOpenAtom, true)
})
```

**`setPendingTestsetSelection`**
```typescript
// Called by EntityPicker's onSelect inside renderModeContent
setPendingTestsetSelection: atom(null, (_get, set, testsetId: string | null) => {
  set(pendingTestsetSelectionAtom, testsetId)
})
```

**`closeAddToTestsetModal`**
```typescript
closeAddToTestsetModal: atom(null, (_get, set) => {
  set(addToTestsetModalOpenAtom, false)
  set(pendingTestsetSelectionAtom, null)
})
```

**`addScenariosToTestset`**
```typescript
addScenariosToTestset: atom(null, async (get, set, payload: {
  targetMode: "existing" | "new"
  commitMessage: string
  newTestsetName?: string   // only when creating a new testset
  newTestsetSlug?: string
}) => Promise<{ jobId: string }>)
```

`addScenariosToTestset` starts a background export job and resolves after the job has been queued. The job itself continues updating `addToTestsetExportJobAtom` until it reaches `"success"` or `"error"`. This keeps the UI responsive for large queues and gives the annotation session root enough state to render a progress indicator.

Note: `targetTestsetId` and `scenarioIds` are **not** passed as payload — the action reads them directly from atoms. The selected target mode is passed because create-vs-existing is a modal choice, not derivable from `pendingTestsetSelectionAtom`.

```
1. Resolve projectId from projectIdAtom
2. Resolve queueKind from queueKindAtom
3. Resolve scope from addToTestsetScopeAtom
   if scope === "all" || scope === "complete" → use get(scenarioIdsAtom)  (all scenarios in session)
   if scope === "selected" → use get(addToTestsetScenarioIdsAtom)          (checked rows)
   if scope === "single"   → use get(addToTestsetScenarioIdsAtom)          (one id)
4. Resolve target mode from payload.targetMode:
   if targetMode === "existing" → require pendingTestsetSelectionAtom and export to that existing testset
   if targetMode === "new" → create a new testset from the exported rows using payload.newTestsetName / payload.newTestsetSlug

5. Create an export job immediately:
     jobId = crypto.randomUUID()
     set(addToTestsetExportJobAtom, { id: jobId, status: "preparing", total: scenarioIds.length, processed: 0, ... })
     start the async job body and return { jobId } to the modal

5b. In the async job body, if targetMode === "existing":
     Fetch the latest revision of targetTestsetId WITH testcases included.
     Strategy: call fetchLatestRevisionsBatch to get the latest revision ID, then call
     fetchRevisionWithTestcases(revisionId) to get the full revision with row data.
     This must use include_testcases: true — fetchLatestRevisionsBatch alone uses
     include_testcases: false and returns no testcase rows, so column names cannot be derived from it.
     Store as `latestRevision`. This result is used in both steps 6 and 8:
       latestRevision.id            → baseRevisionId for patchRevision (step 8)
       latestRevision.data.testcases → derive existingColumns:
           existingColumns = union of all keys across all testcase rows, excluding system fields
           (system fields are those matching SYSTEM_FIELDS from @agenta/entities/testcase)

6. In the async job body, if queueKind === "traces":
     Resolve outputColumnName before building rows:
       if targetMode === "new":
         outputColumnName = "outputs"
       if targetMode === "existing":
         outputColumnName = first match from ["correct_answer", "output", "outputs", "answer"]
                            in existingColumns (resolved in step 5b), fallback to "output" if none found

     For each scenarioId in scenarioIds:
       - get traceRef from store: scenarioTraceRefAtomFamily(scenarioId)
       - get traceInputs from store: traceInputsAtomFamily(traceRef.traceId)
       - get traceOutputs from store: traceOutputsAtomFamily(traceRef.traceId)
       - get annotations from store: scenarioAnnotationsAtomFamily(scenarioId)
         ↑ DO NOT query by traceId directly — use this atom which resolves via
           step-result annotation trace IDs (not invocation trace IDs). Querying
           by invocation traceId causes cross-queue bleed (removed previously).
       - increment addToTestsetExportJobAtom.processed
     rows = buildTraceTestsetRows({ ..., outputColumnName })

7. In the async job body, if queueKind === "testcases":
     testcaseIds = scenarioIds.map(id => scenarioTestcaseRefAtomFamily(id).testcaseId)
     testcases = fetchTestcasesBatch(projectId, testcaseIds)
     annotations = query annotations by testcaseId (batch)
     increment addToTestsetExportJobAtom.processed while rows are prepared
     rows = buildTestcaseExportRows(...)

8. If creating a new testset:
     createTestset({
       projectId,
       name: payload.newTestsetName,
       slug: payload.newTestsetSlug,
       testcases: rows.map(row => row.data),
       commitMessage: payload.commitMessage,
     })
   If exporting to an existing testset:
     Use latestRevision fetched in step 5b (no second fetch needed).
     Compute new column names — keys present in exported rows but absent from existingColumns:
       exportedColumns = union of all keys across rows
       newColumnNames  = exportedColumns − existingColumns
     operations = {
       columns: newColumnNames.length > 0 ? { add: newColumnNames } : undefined,
       rows: { add: rows.map(row => ({ data: row.data })) },
     }
     patchRevision({ projectId, testsetId: targetTestsetId, baseRevisionId: latestRevision.id, operations, message: payload.commitMessage })

9. While the API commit is in flight, set status to "committing".

10. On success:
      set(lastUsedTestsetIdAtom, targetTestsetId)   ← project-scoped, only after confirmed API success
      set(selectedScenarioIdsAtom, [])              ← clear row selection after success
      set(addToTestsetExportJobAtom, { status: "success", processed: rows.length, ... })
      show success toast: "Added {rows.length} rows to {targetTestsetName}"

11. On failure:
      set(addToTestsetExportJobAtom, { status: "error", error: extractApiErrorMessage(err), ... })
      The modal is already closed (it closed after the job was queued in step 5).
      Show a persistent error banner or toast at the session root:
        "Failed to export to {targetTestsetName}: {error message}"
      selectedScenarioIdsAtom is NOT cleared (no rows were written) — the user can re-trigger
      the export from the list view and their row selection is still intact.
```

---

## Package: `agenta-annotation-ui`

### Using `EntityCommitModal` (no new modal component)

The `EntityCommitModal` from `@agenta/entity-ui` is reused directly. No new modal component is needed. The `EntityPicker` is injected via `renderModeContent`, and the testset selection is tracked in `pendingTestsetSelectionAtom` — not in component `useState`.



`EntityCommitModal` requires an `entity` before invoking a custom `onSubmit`; the queue entity is passed only to satisfy the modal shell and title. The actual export target is still controlled by `targetMode` plus `pendingTestsetSelectionAtom`.

**Why atom over `useState` for `pendingTestsetSelectionAtom`:**
`useState` is local to the component instance and is re-initialized on unmount/remount. `EntityCommitModal` uses `destroyOnHidden` which unmounts content on close — any `useState` inside the render closure would reset between opens. Using an atom in the controller means:
- The selection survives re-renders within the open modal
- The action (`addScenariosToTestset`) can read it imperatively without closure capture
- `openAddToTestsetModal` can seed it from `lastUsedTestsetIdAtom` in the same dispatch, with no async gap

---

### Updated Component: `AnnotationPanel.tsx`

**File**: `src/components/AnnotationSession/AnnotationPanel.tsx`

**Change**: Add "Add to Testset" button in the footer action area.

Current footer (when `showMarkComplete` is true):
```
[ Mark completed ]
```

New footer:
```
[ Add to Testset ]  [ Mark completed / Update ]
```

Logic:
- "Add to Testset" is always shown (not gated on `queueKind`)
- On click: `openAddToTestsetModal({ scope: "single", scenarioIds: [scenarioId] })`
- Disabled when `isSubmitting`
- No loading state on the button — the modal starts the export job and the session-level progress indicator handles async state

---

### Updated Component: `FocusView.tsx`

**File**: `src/components/AnnotationSession/FocusView.tsx`

**Change**: `AllCaughtUp` component — add trace queue testset option and upgrade testcase queue button.

Current behaviour:
```
Testcase queue:  [ View previous annotations ]  [ Save to Testset ]   ← auto-fires, no modal
Trace queue:     [ View previous annotations ]  [ Go to observability ]
```

New behaviour:
```
Testcase queue:  [ View previous annotations ]  [ Add to Testset ]    ← opens EntityCommitModal
Trace queue:     [ View previous annotations ]  [ Add to Testset ]  [ Go to observability ]
```

Implementation:
- Remove the `onSyncToTestset` / `isSyncing` props from `FocusView` and `AnnotationSession/index.tsx`
- Both queue kinds call `openAddToTestsetModal({ scope: "complete" })` on button click
- `EntityCommitModal` (mounted at session root) handles the rest

> **Note**: The existing `syncToTestsetsAtom` / `canSyncToTestsetAtom` are **not removed**. They remain on the `annotationSessionController` API surface during transition.

---

### Updated Component: `ScenarioListView.tsx`

**File**: `src/components/AnnotationSession/ScenarioListView.tsx`

**Changes**:

1. **Primary action button**: Replace "Save to testset" (auto-fires `syncToTestsets`) with "Add to Testset" (opens `EntityCommitModal`).

2. **Row selection**: Enable checkbox selection on `InfiniteVirtualTableFeatureShell` via `rowSelection` prop. Track selected row keys in `selectedScenarioIdsAtom` (defined in the controller atoms block, not `useState`) to avoid selection being lost on re-renders. Exposed as:
   - `selectors.selectedScenarioIds()`
   - `actions.setSelectedScenarioIds`

3. **Export scope logic**:
```typescript
const selectedIds = useAtomValue(annotationSessionController.selectors.selectedScenarioIds())
const openModal = useSetAtom(annotationSessionController.actions.openAddToTestsetModal)

const handleAddToTestset = () => {
  openModal(
    selectedIds.length > 0
      ? { scope: "selected", scenarioIds: selectedIds }
      : { scope: "all" }
  )
}
```

4. **Default testset tooltip**: Show the name resolved from `defaultTargetTestsetId()` in the button tooltip. If no default, tooltip reads "Select a testset in the next step".

5. **`canAddToTestset` gating**: Button enabled when `canAddToTestset()` returns true (any queue kind).

---

## Reuse Map

| Need | Reuse |
|------|-------|
| Modal shell | `EntityCommitModal` from `@agenta/entity-ui/modals/commit` |
| Testset selection UI | `EntityPicker` (adapter="testset") from `@agenta/entity-ui`, injected via `renderModeContent` |
| Testset API | `patchRevision`, `createTestset` from `@agenta/entities/testset/api` |
| Latest revision lookup | `fetchLatestRevisionsBatch` from `@agenta/entities/testset` |
| Testcase batch fetch | `fetchTestcasesBatch` from `@agenta/entities/testcase` |
| Testcase row construction | Existing annotation-output selection helpers in `testsetSync.ts`, reused by `buildTestcaseExportRows` |
| Persist last-used testset | `atomWithStorage<Record<string, string \| null>>` from `jotai/utils`, scoped by `projectIdAtom` |
| Trace data access | `traceInputsAtomFamily`, `traceOutputsAtomFamily` from `@agenta/entities/trace` |

---

## State Atom Summary

All transient and persistent state lives in `annotationSessionController.ts`. No `useState` is used for any cross-render or cross-action data in this feature.

| Atom | Persistence | Initialized by | Updated by | Read by |
|------|-------------|----------------|------------|---------|
| `lastUsedTestsetIdAtom` | `localStorage` | first export | `addScenariosToTestset` (on success) | `openAddToTestsetModal`, `defaultTargetTestsetId` selector |
| `lastUsedTestsetByProjectAtom` | `localStorage` | first export per project | `lastUsedTestsetIdAtom` write function | `lastUsedTestsetIdAtom` |
| `pendingTestsetSelectionAtom` | session-only | `openAddToTestsetModal` | `setPendingTestsetSelection` action | `addScenariosToTestset`, `EntityPicker` value prop |
| `addToTestsetExportJobAtom` | session-only | `addScenariosToTestset` | background export job | session progress indicator, retry/error UI |
| `addToTestsetModalOpenAtom` | session-only | `openAddToTestsetModal` | `closeAddToTestsetModal` | `EntityCommitModal` open prop |
| `addToTestsetScopeAtom` | session-only | `openAddToTestsetModal` | — | `addScenariosToTestset`, scope label in modal |
| `addToTestsetScenarioIdsAtom` | session-only | `openAddToTestsetModal` | — | `addScenariosToTestset`; **empty when scope="all" or "complete"** |
| `selectedScenarioIdsAtom` | session-only | user row selection | `setSelectedScenarioIds`; cleared by `addScenariosToTestset` on success | `openAddToTestsetModal` |

---

## Data Mapping Reference

### Trace Queue → Testset Row

Column rules (derived from `extractInputs` / `extractOutputs` in `trace/utils/selectors.ts`):

| Source | Column(s) | Notes |
|--------|-----------|-------|
| `agData.inputs` (`Record<string, unknown>`) | N columns — one per input key | Spread: `question`, `context`, `prompt`, … |
| `agData.outputs` (`unknown`) — existing testset | 1 column; name = first match from `["correct_answer", "output", "outputs", "answer"]` in the target testset's columns; fallback `"output"` | Treated as a single leaf value; never recursed into |
| `agData.outputs` (`unknown`) — new testset | 1 column named `"outputs"` | Same leaf treatment |
| Annotation output field per evaluator | 1 column per evaluator field key | Example: `correctness.score`; only included when a value was submitted |

The `outputColumnName` is resolved once in `addScenariosToTestset` (before row construction) and passed into `buildTraceTestsetRows` as a parameter, so the builder itself has no knowledge of target mode or existing columns.

Example — adding to an existing testset that has a `correct_answer` column:
```
ag.data.inputs:  { question: "What is X?", context: "Y" }
ag.data.outputs: "The answer is Z"
Annotation:      evaluator key "correctness", output field "score", value 0.9
outputColumnName resolved to: "correct_answer"   ← matched existing column

→ Testcase row: {
    question:         "What is X?",        ← from inputs (spread, N columns)
    context:          "Y",                 ← from inputs (spread, N columns)
    correct_answer:   "The answer is Z",   ← single output column, matched existing
    "correctness.score": 0.9              ← annotation column per evaluator field key
  }
```

Example — creating a new testset:
```
outputColumnName resolved to: "outputs"   ← new testset default

→ Testcase row: {
    question:  "What is X?",
    context:   "Y",
    outputs:   "The answer is Z",
    "correctness.score": 0.9
  }
```

The output value may be a plain string, a JSON object, a chat message array, or any other type — the column stores it as-is. The single-column treatment matches `collectKeyPaths` in `selectors.ts` which explicitly does not recurse into `outputs`.

### Testcase Queue → Selected Target Testset

Testcase data is emitted as new rows in the user-selected target testset, or in the newly created testset. Source testset IDs are not used for routing, and the export does not fan out writes across the queue's original source testsets.

```
Testcase:    { input: "What is X?", expected: "Z" }
Annotation:  evaluator key "correctness", output field "score", value 0.9

→ New row: {
    input:       "What is X?",
    expected:    "Z",
    "correctness.score": 0.9
  }
```

---

## Migration & Compatibility

- `syncToTestsetsAtom` / `canSyncToTestsetAtom` are **not removed** — kept for any callers outside `agenta-annotation-ui`.
- `onSyncToTestset` / `isSyncing` props on `FocusView` and `AnnotationSession` are removed since `EntityCommitModal` is now self-contained at session root.
- `ScenarioListView`'s `primaryActionsNode` is updated to use the new modal path.

---

## Implementation Phases

### Phase 1 — Controller atoms + actions + annotate tab button
Files changed:
- `agenta-annotation/src/state/testsetSync.ts` — add `buildTraceTestsetRows`, `buildTestcaseExportRows`
- `agenta-annotation/src/state/controllers/annotationSessionController.ts` — add all new atoms + actions
- `agenta-annotation-ui/src/components/AnnotationSession/index.tsx` — mount `EntityCommitModal`, remove old sync wiring
- `agenta-annotation-ui/src/components/AnnotationSession/AnnotationPanel.tsx` — add "Add to Testset" button

### Phase 2 — Update AllCaughtUp state (done screen)
Files changed:
- `agenta-annotation-ui/src/components/AnnotationSession/FocusView.tsx` — AllCaughtUp redesign for both queue kinds

### Phase 3 — ScenarioListView row selection + upgraded button
Files changed:
- `agenta-annotation-ui/src/components/AnnotationSession/ScenarioListView.tsx` — row selection atom + modal trigger

---

## Verification Plan

| Scenario | Steps | Expected |
|----------|-------|---------|
| Annotate tab — trace queue | Annotate scenario, click "Add to Testset" | Modal opens, no testset pre-selected (no last-used yet) |
| Annotate tab — testcase queue | Annotate scenario, click "Add to Testset" | Modal opens, no testset pre-selected (no last-used yet) |
| Last-used persists | Export to testset X, close session, reopen, click "Add to Testset" | Testset X is pre-selected |
| Picker selection survives re-render | Select testset, trigger a re-render, confirm | Selected testset still shown, correct testset used |
| Project-scoped last-used | Export to testset X in project A, switch to project B, open modal | Project B does not preselect project A's testset |
| Done screen — trace queue | Complete all scenarios | "Add to Testset" button appears |
| Done screen — testcase queue | Complete all scenarios | "Add to Testset" opens modal (no auto-fire) |
| All annotations — no row selection | Click "Add to Testset" | Modal scope label shows all scenarios |
| All annotations — 2 rows selected | Select 2 rows, click "Add to Testset" | Modal scope label shows 2 scenarios |
| Create new testset | Choose "Create new", enter name, confirm | New testset appears in testsets list |
| Export to selected existing testset | Choose testset B, confirm | New rows appear in testset B |
| Multi-source testcase queue | Export scenarios whose testcases came from testsets A and B into selected testset C | All exported rows are added to C only; A and B are not patched |
| Large queue background export | Export 200+ scenarios | Modal closes, annotation UI remains usable, progress indicator advances and resolves to success/error |
| Trace → existing testset (has `correct_answer`) | Export trace with inputs `{q, ctx}` and output `ans` to a testset that has a `correct_answer` column | Row has `q`, `ctx`, `correct_answer` columns |
| Trace → new testset | Export trace with inputs `{q, ctx}` and output `ans` via "Create new testset" | Row has `q`, `ctx`, `outputs` columns |
| Annotation values in export | Export annotated scenario with evaluator key `correctness` and output field `score` | Row has `correctness.score` column with annotation value |
