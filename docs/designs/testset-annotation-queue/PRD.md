# PRD: Testset Creation from Annotation Queue

## Status

Draft — ready for review.

## Problem Statement

Users complete annotation queues to enrich their evaluation datasets, but the current UI makes it difficult to save that work back into testsets. The existing testset sync is rigid:

- Works only for **testcase queues** — trace queue results can't be exported to testsets at all.
- Always writes to the **source testset** — no way to target a different testset or create a new one.
- Exports the **entire queue** at once — no support for partial export (individual scenarios or a selected subset).
- **Auto-fires with no user input** — no commit message, no confirmation, no way to review what's being exported.
- **No memory** — every session starts from scratch with no record of where data was previously sent.

As a result, users who complete a trace annotation queue have nowhere to send their results; users who want to curate a subset of testcase annotations cannot do so; and teams that want fine-grained control over their testset versioning are blocked.

## Goals

1. Let users add annotation queue results to any testset — existing or new — from any point in the annotation session.
2. Support per-scenario export, row-selected bulk export, and full-queue export.
3. Work equally for trace queues and testcase queues.
4. Reduce friction by remembering defaults (last used testset, sensible commit message).

## Non-Goals (this phase)

1. A full column-mapping UI for trace → testset field renaming.
2. Evaluation run export (separate domain, separate UI).
3. Multi-project or cross-workspace testset export.
4. Automatic export on queue completion (remains user-initiated).

## Primary Users

1. **Annotation reviewers** completing human evaluation queues who want to capture their labeled data.
2. **Prompt engineers** curating a testset from a set of reviewed traces.
3. **Team leads** building regression suites from annotated production traces.

## Competitive Reference

### LangSmith
| Capability | Supported |
|------------|-----------|
| Create or extend a testset from both test cases and traces | Yes |
| Add a single scenario to a testset | Yes |
| Add to a testset from the focused/annotate tab | Yes |
| Select table rows and add them to a testset | Yes |

LangSmith supports all four capabilities; Agenta currently supports none of them in full.

---

## User Stories

1. As a reviewer annotating scenarios one-by-one, I can add the current scenario to a testset immediately after annotating it, without waiting to finish the entire queue.
2. As a reviewer who just finished annotating all scenarios, I see a clear call-to-action to save my work to a testset.
3. As a reviewer in the all-annotations list, I can select specific rows and export only those to a testset.
4. As a reviewer using a trace queue, I have the same testset export options as a testcase queue reviewer.
5. As a frequent user, the system remembers which testset I last used and pre-fills it as the default.
6. As a user, I can write a short commit message to document what changed in the testset version.
7. As a user, I can create a brand-new testset from the export flow without leaving the annotation session.

---

## Functional Requirements

### FR1 — Annotate Tab (Per-Scenario Export)
- An "Add to Testset" button must appear in the `AnnotationPanel` footer, alongside the existing "Mark completed" button.
- The button is enabled whenever the current scenario has data that can be exported (regardless of whether it is marked complete).
- Clicking opens the **Commit Modal** (see FR4) scoped to the current scenario only.
- Applies to both trace queues and testcase queues.

### FR2 — "Done with Queue" Screen
- When all scenarios in the session are annotated (`progress.remaining === 0`), the `AllCaughtUp` state must offer "Add to Testset" for **both** queue kinds.
  - Testcase queue: upgrade the existing "Save to Testset" button to open the Commit Modal.
  - Trace queue: add a new "Add to Testset" button alongside the existing "Go to observability" button.
- The Commit Modal scope for this entry point is all scenarios in the queue.

### FR3 — All Annotations Tab (Bulk Export)
- The "Save to testset" primary action in `ScenarioListView` must open the **Commit Modal** (not auto-fire).
- When one or more table rows are selected, only those rows are included in the export scope.
- When no rows are selected, all scenarios are in scope.
- A tooltip on the button should indicate the inferred default target testset (see FR5).
- Applies to both trace queues and testcase queues.

### FR4 — Commit Modal
The Commit Modal is a reusable export modal flow, implemented with the existing entity commit modal shell where possible, with the following elements:

| Element | Description |
|---------|-------------|
| **Target testset selector** | `EntityPicker` (adapter="testset") — browse and select any project testset, or choose "Create new testset" |
| **New testset name field** | Shown only when "Create new testset" is selected |
| **Commit message field** | Free-text, pre-populated with a sensible default (see FR5) |
| **Scope summary** | Read-only label showing how many scenarios will be exported |
| **Confirm / Cancel** | Standard modal footer |

The modal must:
- Pre-select the **default target testset** (see FR5) on open.
- Pre-populate the commit message with a default (see FR5).
- Update the persisted last-used testset on successful commit.
- Show a success toast on completion with a summary (e.g., "Added 3 rows to My Testset").
- If the export fails after the modal has closed, show a persistent error banner or toast at the session root with the failure message (e.g., "Failed to export to My Testset: \<reason\>"). The user can re-open the export flow to retry; the row selection is preserved so no re-selection is needed.

### FR5 — Default Target Testset & Commit Message Heuristics

#### Default target testset
| Scenario | Default Target |
|----------|----------------|
| Testcase queue, first time | No default — user must select |
| Testcase queue, after previous commit | Last committed testset |
| Trace queue, first time | No default — user must select |
| Trace queue, after previous commit | Last committed testset |
| Any queue, after previous commit | Last committed testset (persisted via `atomWithStorage`) |

Testcase queues may contain scenarios from multiple source testsets. The new export flow does not infer or fan out writes to those source testsets. The user always chooses one target testset in the modal, or creates a new one.

#### Default commit message
| Entry point | Default message |
|-------------|-----------------|
| Annotate tab (single scenario) | `"Added scenario from [queue name]"` |
| All annotations tab (multi/all) | `"[queue name]: annotated [N] scenarios"` |
| Done with queue | `"[queue name]: completed annotation queue"` |

The user can freely edit the commit message before confirming.

### FR6 — Trace Queue Export Data Mapping
When exporting from a trace queue, the testset rows are built as follows:

| Source | Testcase column |
|--------|-----------------|
| Trace input key (e.g., `question`) | Column named `question` |
| Additional trace input keys | One column per key |
| Trace output — adding to existing testset | First matching column from `correct_answer`, `output`, `outputs`, `answer`; falls back to `output` if the testset has none of those |
| Trace output — creating new testset | Column named `outputs` |
| Annotation output field per evaluator | Column named using the evaluator field key (e.g., `correctness.score`) |

If the target testset already has named columns, new rows adopt the same column schema. Extra source fields that don't match existing columns are added as new columns.

### FR7 — Testcase Queue Export Data Mapping

Testcase queue export always writes to the user-selected target testset, or to the new testset created from the modal. Even if the selected target is one of the queue's original source testsets, the export action is target-driven and creates rows in that selected target; it does not automatically route each testcase back to its own source testset.

New rows contain:
- All testcase data fields (`input`, `output`, and any custom fields)
- Annotation output fields appended as evaluator field key columns (e.g., `correctness.score`)

---

## Non-Functional Requirements

1. The commit modal must open in < 300ms (testset list is lazy-loaded).
2. The last-used testset must be persisted in `localStorage` (scoped to project ID) and survive page reloads.
3. Export operations should not block the UI — show a loading state and allow the user to continue annotating.
4. For large queues (200+ scenarios), the export should run in the background and show a progress indicator.

---

## Success Metrics

1. % of annotation sessions that result in a testset export (target: increase from ~0% for trace queues to >20% within 30 days of launch).
2. Time-to-export after queue completion (target: < 60 seconds for users who know what testset to use).
3. User retention on the annotation flow — adding per-scenario export should reduce the friction of needing to complete the entire queue before saving.
