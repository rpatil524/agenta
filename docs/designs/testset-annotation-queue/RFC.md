# RFC: Testset Creation from Annotation Queue — Technical Design

## Status

Draft.

## Summary

This RFC describes the frontend-only implementation of testset export from annotation queues. No new backend API endpoints are required; all export operations use the existing `patchRevision` and `createTestset` API functions. The changes are concentrated in two packages:

- `web/packages/agenta-annotation` — new controller actions and state atoms
- `web/packages/agenta-annotation-ui` — new `AddToTestsetModal` and updates to three existing components

---

## Architecture Overview

```
User action (button click)
        │
        ▼
openAddToTestsetModal({ scope, scenarioIds? })   ← new controller action
        │
        ▼
AddToTestsetModal                                 ← new component
  ├── EntityPicker (adapter="testset")            ← existing, @agenta/entity-ui
  ├── Testset name field (create-new mode)
  └── Commit message field
        │
        ▼ (on confirm)
addScenariosToTestset({ scenarioIds, targetTestsetId, commitMessage, ... })  ← new action
        │
        ├─ trace queue path ─────────────────────────────────────────────────┐
        │   buildTraceTestsetRows()                                          │
        │     → fetch trace inputs/outputs (traceInputsAtomFamily, etc.)     │
        │     → fetch annotations for each scenario                          │
        │     → construct row objects                                        │
        │   patchRevision() / createTestset()                                │
        │                                                                    │
        └─ testcase queue path ──────────────────────────────────────────────┘
            if target === source testset:
              buildTestsetSyncPreview() → buildTestsetSyncOperations() → patchRevision()
            if target ≠ source testset:
              buildTestcaseExportRows() → patchRevision() / createTestset()
```

---

## Package: `agenta-annotation`

### File: `src/state/testsetSync.ts` — additions

Add two new builder functions alongside the existing ones:

#### `buildTraceTestsetRows`
```typescript
interface TraceTestsetRowBuilderParams {
  scenarioIds: string[]
  traceInputsByScenario: Map<string, Record<string, unknown>>
  traceOutputsByScenario: Map<string, unknown>
  annotationsByScenario: Map<string, Record<string, unknown>>  // { [evaluatorSlug]: value }
}

interface TraceTestsetRow {
  scenarioId: string
  data: Record<string, unknown>   // { input keys..., output, [evaluator slugs...] }
}

export function buildTraceTestsetRows(params: TraceTestsetRowBuilderParams): TraceTestsetRow[]
```

Logic:
1. For each `scenarioId` in `params.scenarioIds`:
   - Spread all trace input key→value pairs into `data`
   - Add `output` key with the trace output value
   - For each evaluator slug with an annotation value, add it as a column
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

Logic: Same as `buildTestsetSyncPreview` row construction but without the "must be completed" filter and without the "source testset" constraint. Produces rows suitable for `patchRevision` `add` operations.

---

### File: `src/state/controllers/annotationSessionController.ts` — additions

#### New atoms

```typescript
// Persisted across page loads, scoped per project
const lastUsedTestsetIdAtom = atomWithStorage<string | null>(
  "agenta:annotation:last-testset-id",
  null,
  stringStorage
)

// Transient — modal open/close state
const addToTestsetModalOpenAtom = atom<boolean>(false)

// Which scenarios are in scope for the pending export
type AddToTestsetScope = "single" | "selected" | "all"
const addToTestsetScopeAtom = atom<AddToTestsetScope>("all")
const addToTestsetScenarioIdsAtom = atom<string[]>([])
```

#### New selectors (exposed on `annotationSessionController.selectors`)

| Selector | Returns | Description |
|----------|---------|-------------|
| `defaultTargetTestsetId()` | `string \| null` | Heuristic-based default: last used testset if set; otherwise source testset (testcase queues only) |
| `sourceTestsetId()` | `string \| null` | The testset the queue was seeded from (testcase queues only, derived from testcase `testset_id`) |
| `isAddToTestsetModalOpen()` | `boolean` | Whether the commit modal is open |
| `addToTestsetScope()` | `AddToTestsetScope` | Current export scope |
| `addToTestsetScenarioIds()` | `string[]` | Scenario IDs in current export scope |
| `canAddToTestset()` | `boolean` | True when at least one scenario has exportable data (any queue kind) |

#### New actions (exposed on `annotationSessionController.actions`)

**`openAddToTestsetModal`**
```typescript
// atom setter signature
openAddToTestsetModal: atom(null, (get, set, payload: {
  scope: AddToTestsetScope,
  scenarioIds?: string[]      // required when scope === "single" or "selected"
}) => {
  set(addToTestsetScopeAtom, payload.scope)
  set(addToTestsetScenarioIdsAtom, payload.scenarioIds ?? [])
  set(addToTestsetModalOpenAtom, true)
})
```

**`closeAddToTestsetModal`**
```typescript
closeAddToTestsetModal: atom(null, (_get, set) => {
  set(addToTestsetModalOpenAtom, false)
})
```

**`addScenariosToTestset`**
```typescript
// atom setter signature
addScenariosToTestset: atom(null, async (get, set, payload: {
  scenarioIds: string[]
  targetTestsetId: string | null   // null = create new
  newTestsetName?: string
  commitMessage: string
}) => Promise<{ testsetId: string, revisionId: string, rowsAdded: number }>)
```

Internal logic:

```
1. Resolve projectId from projectIdAtom
2. Resolve queueKind from queueKindAtom
3. If payload.targetTestsetId is null:
     createTestset({ name: payload.newTestsetName, testcases: [] })
     targetTestsetId = created testset id

4. Fetch latestRevision for targetTestsetId (fetchLatestRevisionsBatch)

5. If queueKind === "traces":
     For each scenarioId in payload.scenarioIds:
       - get traceRef from scenarioTraceRefAtomFamily(scenarioId)
       - get traceInputs from jotai store (traceInputsAtomFamily)
       - get traceOutputs from jotai store (traceOutputsAtomFamily)
       - query annotations for traceId
     rows = buildTraceTestsetRows(...)

6. If queueKind === "testcases":
     testcaseIds = scenarioIds.map(id => scenarioTestcaseRefAtomFamily(id).testcaseId)
     testcases = fetchTestcasesBatch(projectId, testcaseIds)
     annotations = query annotations by testcaseId (batch)
     if targetTestsetId === sourceTestsetId:
       use existing buildTestsetSyncPreview + buildTestsetSyncOperations path
     else:
       rows = buildTestcaseExportRows(...)

7. operations = rows.map(row => ({ op: "add", data: row.data }))
8. patchRevision({ projectId, testsetId: targetTestsetId, baseRevisionId, operations, message: payload.commitMessage })

9. set(lastUsedTestsetIdAtom, targetTestsetId)
10. return { testsetId: targetTestsetId, revisionId: ..., rowsAdded: rows.length }
```

---

## Package: `agenta-annotation-ui`

### New Component: `AddToTestsetModal`

**Location**: `src/components/AddToTestsetModal/index.tsx`

```
AddToTestsetModal
  ├── EnhancedModal (title="Add to Testset")
  │   ├── ModalContent
  │   │   ├── Scope summary (read-only Text: "X scenarios will be exported")
  │   │   ├── Mode toggle: "Add to existing" | "Create new"
  │   │   ├── [Add to existing mode]
  │   │   │   └── EntityPicker
  │   │   │         adapter="testset"
  │   │   │         variant="list-popover"
  │   │   │         defaultValue={defaultTargetTestsetId}
  │   │   │         onSelect={setSelectedTestset}
  │   │   ├── [Create new mode]
  │   │   │   └── Input (testset name)
  │   │   └── Input (commit message, pre-filled with default)
  │   └── ModalFooter
  │       ├── Button "Cancel"
  │       └── Button "Add to Testset" (primary, loading state)
  └── (reads open state from controller selector)
```

Props:
```typescript
interface AddToTestsetModalProps {
  queueId: string
  onSuccess?: (result: { testsetId: string, rowsAdded: number }) => void
}
```

The component reads `isAddToTestsetModalOpen()`, `addToTestsetScope()`, `addToTestsetScenarioIds()`, `defaultTargetTestsetId()` from `annotationSessionController.selectors` and dispatches `addScenariosToTestset` / `closeAddToTestsetModal` actions.

**Placement**: `AddToTestsetModal` is rendered once at the `AnnotationSession` root (same level as `FocusView`/`ScenarioListView`) so it's always mounted during a session.

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
- Disabled state: same as "Mark completed" (when `isSubmitting`)
- No loading state needed on the button itself — the modal handles async

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
Testcase queue:  [ View previous annotations ]  [ Add to Testset ]    ← opens Commit Modal
Trace queue:     [ View previous annotations ]  [ Add to Testset ]  [ Go to observability ]
```

Implementation:
- Remove the `onSyncToTestset` / `isSyncing` prop wiring from `FocusView` (and from `AnnotationSession/index.tsx`)
- Both queue kinds use `openAddToTestsetModal({ scope: "all" })` on button click
- `AddToTestsetModal` handles the actual export

> **Note**: The existing `syncToTestsetsAtom` / `canSyncToTestsetAtom` can be deprecated once the new flow is fully adopted. Keep them during transition for any callers outside of `agenta-annotation-ui`.

---

### Updated Component: `ScenarioListView.tsx`

**File**: `src/components/AnnotationSession/ScenarioListView.tsx`

**Changes**:

1. **Primary action button**: Replace "Save to testset" (which auto-fires `syncToTestsets`) with "Add to Testset" (which opens the Commit Modal).

2. **Row selection**: `InfiniteVirtualTableFeatureShell` supports row selection via `rowSelection` prop. Enable checkbox selection on the table and track selected row keys in local state.

3. **Export scope logic**:
   ```typescript
   const selectedScenarioIds: string[] = /* from row selection state */
   
   const handleAddToTestset = () => {
     if (selectedScenarioIds.length > 0) {
       openAddToTestsetModal({ scope: "selected", scenarioIds: selectedScenarioIds })
     } else {
       openAddToTestsetModal({ scope: "all" })
     }
   }
   ```

4. **Default testset tooltip**: Show the name of `defaultTargetTestsetId()` in the button tooltip (e.g., "Will default to: My Testset"). If no default, tooltip reads "Select a testset in the next step".

5. **canAddToTestset gating**: Button enabled when `canAddToTestset()` selector returns true (any queue kind, any data available).

---

## Reuse Map

| Need | Reuse |
|------|-------|
| Testset selection UI | `EntityPicker` (adapter="testset", variant="list-popover") from `@agenta/entity-ui` |
| Modal shell | `EnhancedModal` + `ModalContent` + `ModalFooter` from `@agenta/ui` |
| Testset API | `patchRevision`, `createTestset` from `@agenta/entities/testset/api` |
| Latest revision lookup | `fetchLatestRevisionsBatch` from `@agenta/entities/testset` |
| Testcase batch fetch | `fetchTestcasesBatch` from `@agenta/entities/testcase` |
| Testcase queue sync ops | `buildTestsetSyncOperations`, `remapTargetRowsToBaseRevision` from `testsetSync.ts` |
| Persist last-used testset | `atomWithStorage` + `stringStorage` from `jotai/utils` / `@agenta/shared` |
| Trace data access | `traceInputsAtomFamily`, `traceOutputsAtomFamily` from `@agenta/entities/trace` |

---

## Data Mapping Reference

### Trace Queue → Testset Row

Given a scenario backed by trace `T` with evaluator `E`:

```
Trace inputs:   { question: "What is X?", context: "Y" }
Trace output:   "The answer is Z"
Annotation:     { correctness: 0.9 }   (evaluator slug: "correctness")

→ Testcase row: {
    question:    "What is X?",
    context:     "Y",
    output:      "The answer is Z",
    correctness: 0.9
  }
```

### Testcase Queue → Same Testset (source testset)

Uses existing `buildTestsetSyncPreview` + `buildTestsetSyncOperations`. Annotation values are merged as new columns into existing rows matched by `testcase_id`. Original input/output data is preserved.

### Testcase Queue → Different Testset

Testcase data is re-emitted as new rows (no `testcase_id` merging — the target testset has different rows):

```
Testcase:    { input: "What is X?", expected: "Z" }
Annotation:  { correctness: 0.9 }

→ New row: {
    input:       "What is X?",
    expected:    "Z",
    correctness: 0.9
  }
```

---

## Migration & Compatibility

- The existing `syncToTestsetsAtom` and `canSyncToTestsetAtom` are **not removed** in this change. They remain on the `annotationSessionController` API surface.
- The `onSyncToTestset` / `isSyncing` props on `FocusView` and `AnnotationSession` are removed as part of this change since `AddToTestsetModal` is self-contained.
- `ScenarioListView`'s `primaryActionsNode` is updated to use the new modal path.

---

## Implementation Phases

### Phase 1 — Modal infrastructure + Annotate tab button
Files changed:
- `agenta-annotation/src/state/testsetSync.ts` — add `buildTraceTestsetRows`, `buildTestcaseExportRows`
- `agenta-annotation/src/state/controllers/annotationSessionController.ts` — add atoms + actions
- `agenta-annotation-ui/src/components/AddToTestsetModal/index.tsx` — new component
- `agenta-annotation-ui/src/components/AnnotationSession/AnnotationPanel.tsx` — add button
- `agenta-annotation-ui/src/components/AnnotationSession/index.tsx` — mount modal, remove old sync wiring

### Phase 2 — Update AllCaughtUp state + Done screen
Files changed:
- `agenta-annotation-ui/src/components/AnnotationSession/FocusView.tsx` — AllCaughtUp redesign

### Phase 3 — ScenarioListView row selection + upgraded button
Files changed:
- `agenta-annotation-ui/src/components/AnnotationSession/ScenarioListView.tsx` — row selection + modal

---

## Verification Plan

| Scenario | Steps | Expected |
|----------|-------|---------|
| Annotate tab — trace queue | Annotate scenario, click "Add to Testset" | Modal opens with no default testset pre-selected |
| Annotate tab — testcase queue | Annotate scenario, click "Add to Testset" | Modal opens with source testset pre-selected |
| Annotate tab — last used persists | Export to testset X, close session, reopen, click "Add to Testset" | Testset X is pre-selected |
| Done screen — trace queue | Complete all scenarios | "Add to Testset" button appears |
| Done screen — testcase queue | Complete all scenarios | "Add to Testset" button opens modal (not auto-fires) |
| All annotations — no selection | Click "Add to Testset" | Modal scope summary shows all scenarios |
| All annotations — 2 rows selected | Select 2 rows, click "Add to Testset" | Modal scope summary shows 2 scenarios |
| Create new testset | Choose "Create new", enter name, confirm | New testset appears in testsets list |
| Export to different testset | Choose testset B (not source), confirm | New rows appear in testset B |
| Trace → testset data check | Export trace scenario with inputs `{q, ctx}` and output `ans` | Testset row has `q`, `ctx`, `output` columns |
| Annotation values in export | Export annotated scenario with evaluator "score" | Testset row has `score` column with annotation value |
