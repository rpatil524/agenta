# Testset Creation from Annotation Queue

## Overview

This feature enables users to add annotation queue scenarios (individual or in bulk) to testsets directly from the annotation session UI. It extends the existing narrow "sync to source testset" path to support:

- Per-scenario "Add to Testset" from the annotate (focused) view
- Bulk add from the all-annotations list view, with row-level selection
- "Done" screen (all-caught-up state) surfacing testset creation for both queue kinds
- Testset selection modal — choose any existing testset or create a new one
- Support for **trace queues** (not just testcase queues as today)
- Persisted default target testset (last used per project)

## Documents

| Document | Purpose |
|----------|---------|
| [PRD.md](./PRD.md) | Product requirements, user goals, interaction model, success criteria |
| [RFC.md](./RFC.md) | Technical architecture, data flows, component design, state management |

## Background & Motivation

Annotation queues are a primary mechanism for collecting human feedback on model outputs. The feedback collected is only valuable if it can be written back into a testset for:
- Regression testing with new prompts/variants
- Offline evaluation runs
- Sharing reviewed data with the broader team

Today the write-back path is fragile: it only exists for testcase queues, always points to the source testset, exports the entire queue at once, and requires no user input (which makes it inflexible). For trace queues there is no write-back path at all.

This feature closes that gap by making testset creation a first-class action at every point in the annotation workflow.

## Scope

**In scope:**
- Frontend UI changes in `agenta-annotation-ui` and `agenta-annotation` packages
- New `AddToTestsetModal` component
- Updated controller actions for per-scenario and multi-scenario export
- Trace queue → testset data mapping

**Out of scope:**
- New backend API endpoints (all export operations use existing `patchRevision` / `createTestset`)
- Column mapping UI (data is mapped deterministically; see RFC §Data Mapping)
- Evaluation run export (separate domain)

## Open Questions

1. **Trace → testset column naming**: Should trace input keys be used as-is as testcase column names, or should the user be able to rename them in the commit modal?
2. **Single-scenario "Add to Testset" for testcase queues**: When a user adds a single testcase-queue scenario to a testset that already contains that testcase (by `testcase_id`), should it update the existing row or add a new one?
3. **New testset creation flow**: Should creating a new testset from the commit modal require naming a variant, or use a default variant name (e.g., "default")?
4. **Annotation inclusion**: Should annotation values always be included as extra columns, or should the user be able to opt out per evaluator?
5. **Cross-project testsets**: Should the testset picker be scoped to the current project only, or allow cross-project export?
