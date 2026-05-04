# RFC: Testset Creation from Annotation Queue — Technical Design

## Status

Draft.

## Summary

This RFC describes the frontend-only implementation of testset export from annotation queues. No new backend API endpoints are required; all export operations use the existing `patchRevision` and `createTestset` API functions. The changes are concentrated in two packages:

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
            if target === source testset:
              buildTestsetSyncPreview() → buildTestsetSyncOperations() → patchRevision()
            if target ≠ source testset:
              buildTestcaseExportRows() → patchRevision() / createTestset()
        │
        ▼ (on success)
  set(lastUsedTestsetIdAtom, targetTestsetId)   ← persist after confirmed write
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
  // Always mapped to a single "output" column regardless of shape.
  traceOutputsByScenario: Map<string, unknown>
  // One entry per evaluator slug with a submitted annotation value.
  annotationsByScenario: Map<string, Record<string, unknown>>  // { [evaluatorSlug]: value }
}

interface TraceTestsetRow {
  scenarioId: string
  // Resulting column shape: { ...inputKeys, output: <any>, [evaluatorSlug]: <value>, ... }
  data: Record<string, unknown>
}

export function buildTraceTestsetRows(params: TraceTestsetRowBuilderParams): TraceTestsetRow[]
```

Logic:
1. For each `scenarioId` in `params.scenarioIds`:
   - **Input columns** — spread the `Record<string, unknown>` from `traceInputsByScenario` directly into `data`. Each key becomes its own column (e.g., `question`, `context`, `prompt`). This matches what `traceInputsAtomFamily` returns via `extractInputs()` → `agData.inputs`.
   - **Output column** — add a single `"output"` key whose value is the raw `unknown` from `traceOutputsByScenario`. The value is never split or recursed into; it maps to exactly one column regardless of its type (string, object, chat message, etc.). This matches `extractOutputs()` which deliberately treats `agData.outputs` as a leaf.
   - **Annotation columns** — for each evaluator slug in `annotationsByScenario`, add one column named after the slug. Skip evaluators with no submitted value.
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
  stringStorage,
)

// Transient — modal open/close state
const addToTestsetModalOpenAtom = atom<boolean>(false)

// Which scenarios are in scope for the pending export
type AddToTestsetScope = "single" | "selected" | "all"
const addToTestsetScopeAtom = atom<AddToTestsetScope>("all")
const addToTestsetScenarioIdsAtom = atom<string[]>([])

// The testset currently selected inside the open modal.
// Seeded from defaultTargetTestsetId when modal opens; updated by EntityPicker onSelect.
// Lives here — NOT in component state — so it survives re-renders without data loss.
const pendingTestsetSelectionAtom = atom<string | null>(null)
```

#### New selectors (exposed on `annotationSessionController.selectors`)

| Selector | Returns | Description |
|----------|---------|-------------|
| `defaultTargetTestsetId()` | `string \| null` | Heuristic default: last used testset if set; otherwise source testset (testcase queues only) |
| `sourceTestsetId()` | `string \| null` | The testset the queue was seeded from (testcase queues only, derived from testcase `testset_id`) |
| `lastUsedTestsetId()` | `string \| null` | Persisted last-used testset ID |
| `pendingTestsetSelection()` | `string \| null` | The testset currently selected in the open modal |
| `isAddToTestsetModalOpen()` | `boolean` | Whether the commit modal is open |
| `addToTestsetScope()` | `AddToTestsetScope` | Current export scope |
| `addToTestsetScenarioIds()` | `string[]` | Scenario IDs in current export scope |
| `canAddToTestset()` | `boolean` | True when at least one scenario has exportable data (any queue kind) |

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
  commitMessage: string
  newTestsetName?: string   // only when creating a new testset
  newTestsetSlug?: string
}) => Promise<{ testsetId: string, revisionId: string, rowsAdded: number }>)
```

Note: `targetTestsetId` and `scenarioIds` are **not** passed as payload — the action reads them directly from atoms:

```
1. Resolve projectId from projectIdAtom
2. Resolve queueKind from queueKindAtom
3. Resolve scenarioIds from addToTestsetScenarioIdsAtom
   (if scope === "all", fall back to all scenarioIdsAtom)
4. Resolve targetTestsetId from pendingTestsetSelectionAtom
   If null → create new: createTestset({ name: payload.newTestsetName, slug: payload.newTestsetSlug })
             targetTestsetId = created testset id

5. Fetch latestRevision for targetTestsetId (fetchLatestRevisionsBatch)

6. If queueKind === "traces":
     For each scenarioId in scenarioIds:
       - get traceRef from scenarioTraceRefAtomFamily(scenarioId)
       - get traceInputs from jotai store (traceInputsAtomFamily)
       - get traceOutputs from jotai store (traceOutputsAtomFamily)
       - query annotations for traceId
     rows = buildTraceTestsetRows(...)

7. If queueKind === "testcases":
     testcaseIds = scenarioIds.map(id => scenarioTestcaseRefAtomFamily(id).testcaseId)
     testcases = fetchTestcasesBatch(projectId, testcaseIds)
     annotations = query annotations by testcaseId (batch)
     if targetTestsetId === get(sourceTestsetIdAtom):
       use existing buildTestsetSyncPreview + buildTestsetSyncOperations path
     else:
       rows = buildTestcaseExportRows(...)

8. operations = rows.map(row => ({ op: "add", data: row.data }))
9. patchRevision({ projectId, testsetId: targetTestsetId, baseRevisionId, operations, message: payload.commitMessage })

10. set(lastUsedTestsetIdAtom, targetTestsetId)   ← only after confirmed API success
11. return { testsetId: targetTestsetId, revisionId: ..., rowsAdded: rows.length }
```

---

## Package: `agenta-annotation-ui`

### Using `EntityCommitModal` (no new modal component)

The `EntityCommitModal` from `@agenta/entity-ui` is reused directly. No new modal component is needed. The `EntityPicker` is injected via `renderModeContent`, and the testset selection is tracked in `pendingTestsetSelectionAtom` — not in component `useState`.

```tsx
// Inside the component that renders the modal (AnnotationSession/index.tsx)

const isOpen = useAtomValue(annotationSessionController.selectors.isAddToTestsetModalOpen())
const pendingSelection = useAtomValue(annotationSessionController.selectors.pendingTestsetSelection())
const scope = useAtomValue(annotationSessionController.selectors.addToTestsetScope())
const scenarioIds = useAtomValue(annotationSessionController.selectors.addToTestsetScenarioIds())
const setPendingSelection = useSetAtom(annotationSessionController.actions.setPendingTestsetSelection)
const closeModal = useSetAtom(annotationSessionController.actions.closeAddToTestsetModal)
const addScenariosToTestset = useSetAtom(annotationSessionController.actions.addScenariosToTestset)

const scopeLabel = scope === "single"
  ? "1 scenario"
  : `${scenarioIds.length || "all"} scenarios`

<EntityCommitModal
  open={isOpen}
  onClose={closeModal}
  actionLabel="Add to Testset"
  submitLabel="Add to Testset"
  commitModes={[
    { id: "existing", label: "Add to existing testset" },
    { id: "new",      label: "Create new testset" },
  ]}
  createEntityFields={{ modes: ["new"], nameLabel: "New testset name" }}
  renderModeContent={({ mode }) =>
    mode !== "new" ? (
      <div className="flex flex-col gap-1">
        <label className="font-medium text-sm">Target testset</label>
        <EntityPicker
          adapter="testset"
          variant="list-popover"
          value={pendingSelection}
          onSelect={(result) => setPendingSelection(result.id)}
        />
        <Typography.Text type="secondary" className="text-xs">
          {scopeLabel} will be added as new rows.
        </Typography.Text>
      </div>
    ) : (
      <Typography.Text type="secondary" className="text-xs">
        {scopeLabel} will be added to the new testset.
      </Typography.Text>
    )
  }
  canSubmit={({ mode }) =>
    mode === "new" ? true : pendingSelection !== null
  }
  onSubmit={async ({ mode, message, entityName, entitySlug }) => {
    try {
      await addScenariosToTestset({
        commitMessage: message,
        ...(mode === "new" && { newTestsetName: entityName, newTestsetSlug: entitySlug }),
      })
      return { success: true }
    } catch (err) {
      return { success: false, error: err }
    }
  }}
  onAfterSuccess={() => {
    closeModal()
  }}
/>
```

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
- No loading state on the button — the modal handles async

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
- Both queue kinds call `openAddToTestsetModal({ scope: "all" })` on button click
- `EntityCommitModal` (mounted at session root) handles the rest

> **Note**: The existing `syncToTestsetsAtom` / `canSyncToTestsetAtom` are **not removed**. They remain on the `annotationSessionController` API surface during transition.

---

### Updated Component: `ScenarioListView.tsx`

**File**: `src/components/AnnotationSession/ScenarioListView.tsx`

**Changes**:

1. **Primary action button**: Replace "Save to testset" (auto-fires `syncToTestsets`) with "Add to Testset" (opens `EntityCommitModal`).

2. **Row selection**: Enable checkbox selection on `InfiniteVirtualTableFeatureShell` via `rowSelection` prop. Track selected row keys in an atom (not `useState`) to avoid selection being lost on re-renders:

```typescript
// In annotationSessionController.ts
const selectedScenarioIdsAtom = atom<string[]>([])

// Exposed as:
selectors.selectedScenarioIds()
actions.setSelectedScenarioIds
```

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
| Testcase queue sync ops | `buildTestsetSyncOperations`, `remapTargetRowsToBaseRevision` from `testsetSync.ts` |
| Persist last-used testset | `atomWithStorage` + `stringStorage` from `jotai/utils` / `@agenta/shared` |
| Trace data access | `traceInputsAtomFamily`, `traceOutputsAtomFamily` from `@agenta/entities/trace` |

---

## State Atom Summary

All transient and persistent state lives in `annotationSessionController.ts`. No `useState` is used for any cross-render or cross-action data in this feature.

| Atom | Persistence | Initialized by | Updated by | Read by |
|------|-------------|----------------|------------|---------|
| `lastUsedTestsetIdAtom` | `localStorage` | first export | `addScenariosToTestset` (on success) | `openAddToTestsetModal`, `defaultTargetTestsetId` selector |
| `pendingTestsetSelectionAtom` | session-only | `openAddToTestsetModal` | `setPendingTestsetSelection` action | `addScenariosToTestset`, `EntityPicker` value prop |
| `addToTestsetModalOpenAtom` | session-only | `openAddToTestsetModal` | `closeAddToTestsetModal` | `EntityCommitModal` open prop |
| `addToTestsetScopeAtom` | session-only | `openAddToTestsetModal` | — | scope label in modal |
| `addToTestsetScenarioIdsAtom` | session-only | `openAddToTestsetModal` | — | `addScenariosToTestset` |
| `selectedScenarioIdsAtom` | session-only | user row selection | `setSelectedScenarioIds` | `openAddToTestsetModal` |

---

## Data Mapping Reference

### Trace Queue → Testset Row

Column rules (derived from `extractInputs` / `extractOutputs` in `trace/utils/selectors.ts`):

| Source | Column(s) | Notes |
|--------|-----------|-------|
| `agData.inputs` (`Record<string, unknown>`) | N columns — one per input key | Spread: `question`, `context`, `prompt`, … |
| `agData.outputs` (`unknown`) | 1 column named `"output"` | Treated as a single leaf value; never recursed into, regardless of shape |
| Annotation per evaluator | 1 column per evaluator slug | Only included when a value was submitted |

Example:
```
ag.data.inputs:  { question: "What is X?", context: "Y" }
ag.data.outputs: "The answer is Z"          ← any type; always maps to one "output" column
Annotation:      evaluator slug "correctness", value 0.9

→ Testcase row: {
    question:    "What is X?",   ← from inputs (spread, N columns)
    context:     "Y",            ← from inputs (spread, N columns)
    output:      "The answer is Z",  ← single output column
    correctness: 0.9             ← annotation column per evaluator slug
  }
```

The `output` value may be a plain string, a JSON object, a chat message array, or any other type — the column stores it as-is. The single-column treatment matches `collectKeyPaths` in `selectors.ts` which explicitly does not recurse into `outputs`.

### Testcase Queue → Same Testset (source testset)

Uses existing `buildTestsetSyncPreview` + `buildTestsetSyncOperations`. Annotation values are merged as new columns into existing rows matched by `testcase_id`. Original input/output data is preserved.

### Testcase Queue → Different Testset

Testcase data is re-emitted as new rows (no `testcase_id` merging):

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
| Annotate tab — testcase queue | Annotate scenario, click "Add to Testset" | Modal opens, source testset pre-selected |
| Last-used persists | Export to testset X, close session, reopen, click "Add to Testset" | Testset X is pre-selected |
| Picker selection survives re-render | Select testset, trigger a re-render, confirm | Selected testset still shown, correct testset used |
| Done screen — trace queue | Complete all scenarios | "Add to Testset" button appears |
| Done screen — testcase queue | Complete all scenarios | "Add to Testset" opens modal (no auto-fire) |
| All annotations — no row selection | Click "Add to Testset" | Modal scope label shows all scenarios |
| All annotations — 2 rows selected | Select 2 rows, click "Add to Testset" | Modal scope label shows 2 scenarios |
| Create new testset | Choose "Create new", enter name, confirm | New testset appears in testsets list |
| Export to different testset | Choose testset B (not source), confirm | New rows appear in testset B |
| Trace → testset data check | Export trace with inputs `{q, ctx}` and output `ans` | Row has `q`, `ctx`, `output` columns |
| Annotation values in export | Export annotated scenario with evaluator "score" | Row has `score` column with annotation value |
