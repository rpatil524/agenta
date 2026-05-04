import {memo, useCallback, useEffect, useMemo, useRef} from "react"

import {annotationFormController, annotationSessionController} from "@agenta/annotation"
import type {SessionView} from "@agenta/annotation"
import {simpleQueueMolecule} from "@agenta/entities/simpleQueue"
import {testsetsListAtom, type Testset} from "@agenta/entities/testset"
import {
    EntityCommitModal,
    EntityPicker,
    type CommitSubmitParams,
    type CommitSubmitResult,
    type EntitySelectionAdapter,
    type EntitySelectionResult,
    type ListQueryState,
    type SelectionPathItem,
} from "@agenta/entity-ui"
import {PageLayout} from "@agenta/ui"
import {message} from "@agenta/ui/app-message"
import {Tray} from "@phosphor-icons/react"
import {Button, Spin, Tabs, Typography} from "antd"
import {type Atom, useAtomValue, useSetAtom} from "jotai"

import {useAnnotationNavigation} from "../../context"

import ConfigurationView from "./ConfigurationView"
import FocusView from "./FocusView"
import ScenarioListView from "./ScenarioListView"

// ============================================================================
// TYPES
// ============================================================================

interface AnnotationSessionProps {
    queueId: string
    routeState: {
        view: SessionView
        scenarioId?: string
    }
    onActiveViewChange?: (view: SessionView) => void
    canExportData?: boolean
}

interface AddToTestsetTargetSelection extends EntitySelectionResult<{
    testsetId: string
    testsetName: string
}> {
    type: "testset"
    metadata: {
        testsetId: string
        testsetName: string
    }
}

// ============================================================================
// TAB ITEMS
// ============================================================================

const SESSION_TABS: {key: SessionView; label: string}[] = [
    {key: "annotate", label: "Annotate"},
    {key: "list", label: "All Annotations"},
    {key: "configuration", label: "Configuration"},
]

const TAB_ITEMS = SESSION_TABS.map((t) => ({key: t.key, label: t.label}))

const ADD_TO_TESTSET_COMMIT_MODES = [
    {id: "existing", label: "Existing testset"},
    {id: "new", label: "New testset"},
]

const CREATE_TESTSET_FIELDS = {
    modes: ["new"],
    nameLabel: "Testset name",
    defaultName: ({entity}: {entity: {name?: string} | null}) => entity?.name ?? "",
}

const SessionTitle = memo(function SessionTitle({queueName}: {queueName: string}) {
    return <span className="truncate">{queueName}</span>
})

const ADD_TO_TESTSET_TARGET_ADAPTER: EntitySelectionAdapter<AddToTestsetTargetSelection> = {
    name: "annotation-add-to-testset-target",
    entityType: "testset",
    hierarchy: {
        selectableLevel: 0,
        levels: [
            {
                type: "testset",
                label: "Testset",
                listAtom: testsetsListAtom as unknown as Atom<ListQueryState<Testset>>,
                getId: (testset: unknown) => (testset as Testset).id,
                getLabel: (testset: unknown) => (testset as Testset).name,
                getDescription: (testset: unknown) => (testset as Testset).description ?? undefined,
                hasChildren: () => false,
                isSelectable: () => true,
            },
        ],
    },
    toSelection: (path: SelectionPathItem[], leafEntity: unknown): AddToTestsetTargetSelection => {
        const testset = leafEntity as Testset
        const id = testset.id
        const name = testset.name

        return {
            type: "testset",
            id,
            label: name,
            path,
            metadata: {
                testsetId: id,
                testsetName: name,
            },
        }
    },
    isComplete: (path: SelectionPathItem[]) => Boolean(path[0]?.id),
    emptyMessage: "No testsets found",
    loadingMessage: "Loading testsets...",
}

// ============================================================================
// HEADER RIGHT SECTION
// ============================================================================

const SessionHeaderRight = memo(function SessionHeaderRight({
    activeView,
    onTabChange,
}: {
    activeView: SessionView
    onTabChange: (key: string) => void
}) {
    return (
        <div className="flex items-center gap-4">
            <Tabs
                activeKey={activeView}
                onChange={onTabChange}
                items={TAB_ITEMS}
                className="[&_.ant-tabs-nav]:!mb-0"
                size="small"
            />
        </div>
    )
})

// ============================================================================
// EMPTY QUEUE STATE
// ============================================================================

const EmptyQueueState = memo(function EmptyQueueState({
    onViewChange,
}: {
    onViewChange: (view: SessionView) => void
}) {
    const navigation = useAnnotationNavigation()
    const queueKind = useAtomValue(annotationSessionController.selectors.queueKind())
    const isTraces = queueKind === "traces"

    return (
        <div className="flex flex-col flex-1 items-center justify-center gap-4 min-h-0">
            <div className="flex items-center justify-center size-20 rounded-full bg-[var(--ant-color-fill-quaternary)]">
                <Tray size={32} className="text-[var(--ant-color-text-secondary)]" />
            </div>

            <div className="flex flex-col items-center gap-2 text-center">
                <Typography.Text strong className="!text-base">
                    There&apos;s nothing to see here
                </Typography.Text>
                <Typography.Text type="secondary" className="text-sm">
                    Currently there are no runs &amp; annotations in this queue,
                    <br />
                    {isTraces ? "please add runs from traces." : "please add items from test sets."}
                </Typography.Text>
            </div>

            <div className="flex items-center gap-2">
                <Button size="small" onClick={() => onViewChange("list")}>
                    View previous annotations
                </Button>
                {isTraces && navigation.navigateToObservability && (
                    <Button
                        size="small"
                        type="primary"
                        className="!bg-[#051729] !border-[#051729] hover:!bg-[#0a2540] hover:!border-[#0a2540]"
                        onClick={() => navigation.navigateToObservability?.()}
                    >
                        Go to observability
                    </Button>
                )}
            </div>
        </div>
    )
})

// ============================================================================
// MAIN COMPONENT
// ============================================================================

const AnnotationSession = ({
    queueId,
    routeState,
    onActiveViewChange,
    canExportData = true,
}: AnnotationSessionProps) => {
    // Queue data from molecule (auto-fetched by queueId)
    const queueQuery = useAtomValue(simpleQueueMolecule.selectors.query(queueId))
    const queue = useAtomValue(simpleQueueMolecule.selectors.data(queueId))
    const initialRouteStateRef = useRef(routeState)
    useEffect(() => {
        initialRouteStateRef.current = routeState
    })

    // Session controller actions
    const openQueue = useSetAtom(annotationSessionController.actions.openQueue)
    const closeSession = useSetAtom(annotationSessionController.actions.closeSession)
    const applyRouteState = useSetAtom(annotationSessionController.actions.applyRouteState)
    const setActiveView = useSetAtom(annotationSessionController.actions.setActiveView)
    const syncScenarioOrder = useSetAtom(annotationSessionController.actions.syncScenarioOrder)
    const closeAddToTestsetModal = useSetAtom(
        annotationSessionController.actions.closeAddToTestsetModal,
    )
    const setPendingTestsetSelection = useSetAtom(
        annotationSessionController.actions.setPendingTestsetSelection,
    )
    const addScenariosToTestset = useSetAtom(
        annotationSessionController.actions.addScenariosToTestset,
    )

    // Session controller selectors — queue-level
    const queueName = useAtomValue(annotationSessionController.selectors.queueName())
    const controllerActiveView = useAtomValue(annotationSessionController.selectors.activeView())
    const resolvedActiveView = controllerActiveView
    const isAddToTestsetModalOpen = useAtomValue(
        annotationSessionController.selectors.isAddToTestsetModalOpen(),
    )
    const pendingTestsetSelection = useAtomValue(
        annotationSessionController.selectors.pendingTestsetSelection(),
    )
    const addToTestsetExportJob = useAtomValue(
        annotationSessionController.selectors.addToTestsetExportJob(),
    )
    const isAddToTestsetExporting = useAtomValue(
        annotationSessionController.selectors.isAddToTestsetExporting(),
    )
    // Scenarios — derived reactively from simpleQueueMolecule via the controller
    const allScenarioIds = useAtomValue(annotationSessionController.selectors.scenarioIds())
    const scenarioCount = allScenarioIds.length
    const scenariosQuery = useAtomValue(annotationSessionController.selectors.scenariosQuery())
    const notifiedExportJobIdRef = useRef<string | null>(null)

    // Open the session when queueId is set
    useEffect(() => {
        if (!queueId) return

        const initialRouteState = initialRouteStateRef.current
        openQueue({
            queueId,
            queueType: "simple",
            initialView: initialRouteState.view,
            initialScenarioId: initialRouteState.scenarioId ?? null,
        })

        return () => {
            closeSession()
            annotationFormController.set.clearFormState()
        }
    }, [queueId, closeSession, openQueue])

    useEffect(() => {
        applyRouteState({
            view: routeState.view,
            scenarioId: routeState.scenarioId,
        })
    }, [applyRouteState, routeState.view, routeState.scenarioId, scenarioCount])

    useEffect(() => {
        syncScenarioOrder()
    }, [syncScenarioOrder, scenariosQuery.data])

    // Callbacks for AnnotationPanel notifications
    const handleSaved = useCallback(() => {
        message.success("Annotations saved")
    }, [])

    const handleCompleted = useCallback((scenarioId: string) => {
        message.success("Scenario completed")
    }, [])

    const handleActiveViewChange = useCallback(
        (nextView: SessionView) => {
            setActiveView(nextView)
            if (nextView !== controllerActiveView) {
                onActiveViewChange?.(nextView)
            }
        },
        [controllerActiveView, onActiveViewChange, setActiveView],
    )

    const handleTabChange = useCallback(
        (key: string) => {
            handleActiveViewChange(key as SessionView)
        },
        [handleActiveViewChange],
    )

    useEffect(() => {
        if (!addToTestsetExportJob.id) return
        if (notifiedExportJobIdRef.current === addToTestsetExportJob.id) return

        if (addToTestsetExportJob.status === "success") {
            notifiedExportJobIdRef.current = addToTestsetExportJob.id
            message.success(
                `Added ${addToTestsetExportJob.processed} row${
                    addToTestsetExportJob.processed === 1 ? "" : "s"
                } to ${addToTestsetExportJob.targetTestsetName ?? "testset"}`,
            )
        }
    }, [addToTestsetExportJob])

    const handleTestsetSelect = useCallback(
        (selection: AddToTestsetTargetSelection) => {
            setPendingTestsetSelection({
                testsetId: selection.metadata.testsetId,
                testsetName: selection.metadata.testsetName,
            })
        },
        [setPendingTestsetSelection],
    )

    const handleTestsetDeselect = useCallback(() => {
        setPendingTestsetSelection({testsetId: null})
    }, [setPendingTestsetSelection])

    const handleAddToTestsetModeChange = useCallback(
        (mode: string | undefined) => {
            if (mode === "new") {
                setPendingTestsetSelection({testsetId: null})
            }
        },
        [setPendingTestsetSelection],
    )

    const handleAddToTestsetSubmit = useCallback(
        async (params: CommitSubmitParams): Promise<CommitSubmitResult> => {
            try {
                await addScenariosToTestset({
                    targetMode: params.mode === "new" ? "new" : "existing",
                    commitMessage: params.message,
                    newTestsetName: params.entityName,
                    newTestsetSlug: params.entitySlug,
                })
                return {success: true}
            } catch (error) {
                return {
                    success: false,
                    error:
                        error instanceof Error && error.message
                            ? error.message
                            : "Failed to start testset export",
                }
            }
        },
        [addScenariosToTestset],
    )

    const canSubmitAddToTestset = useCallback(
        ({mode}: {mode?: string}) => {
            if (isAddToTestsetExporting) return false
            if (mode === "new") return true
            return Boolean(pendingTestsetSelection)
        },
        [isAddToTestsetExporting, pendingTestsetSelection],
    )

    const renderAddToTestsetModeContent = useCallback(
        ({mode}: {mode?: string}) => (
            <div className="flex flex-col gap-3">
                {mode !== "new" && (
                    <EntityPicker<AddToTestsetTargetSelection>
                        variant="cascading"
                        adapter={ADD_TO_TESTSET_TARGET_ADAPTER}
                        initialSelections={[pendingTestsetSelection]}
                        showLabels
                        showAutoIndicator={false}
                        placeholders={["Select testset"]}
                        onSelect={handleTestsetSelect}
                        onDeselect={handleTestsetDeselect}
                    />
                )}
            </div>
        ),
        [handleTestsetSelect, handleTestsetDeselect, pendingTestsetSelection],
    )

    // Header right section (tabs + sync button)
    const headerTabs = useMemo(
        () => <SessionHeaderRight activeView={resolvedActiveView} onTabChange={handleTabChange} />,
        [resolvedActiveView, handleTabChange],
    )

    const headerTitle = useMemo(
        () => <SessionTitle queueName={queueName || "Untitled Queue"} />,
        [queueName],
    )

    // Loading state — queue query or scenarios query pending
    const isLoading = queueQuery.isPending || (queue && scenariosQuery.isPending)

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-full py-20">
                <Spin size="large" />
            </div>
        )
    }

    // Queue not found
    if (!queue) {
        return (
            <div className="flex items-center justify-center h-full py-20">
                <Typography.Text type="secondary">Queue not found</Typography.Text>
            </div>
        )
    }

    return (
        <PageLayout
            title={headerTitle}
            titleLevel={4}
            headerTabs={headerTabs}
            className="!p-0 h-full min-h-0 !gap-2"
            headerClassName="px-4"
        >
            {/* Content */}
            <div className="flex-1 flex flex-col overflow-hidden min-h-0">
                {resolvedActiveView === "configuration" ? (
                    <ConfigurationView queueId={queueId} />
                ) : scenarioCount === 0 ? (
                    <EmptyQueueState onViewChange={handleActiveViewChange} />
                ) : resolvedActiveView === "list" ? (
                    <ScenarioListView
                        queueId={queueId}
                        onSaved={handleSaved}
                        onCompleted={handleCompleted}
                        onViewChange={handleActiveViewChange}
                        canExportData={canExportData}
                    />
                ) : (
                    <FocusView
                        queueId={queueId}
                        onCompleted={handleCompleted}
                        onViewChange={handleActiveViewChange}
                    />
                )}
            </div>
            <EntityCommitModal
                open={isAddToTestsetModalOpen}
                onClose={closeAddToTestsetModal}
                entity={{
                    type: "simpleQueue",
                    id: queueId,
                }}
                onSubmit={handleAddToTestsetSubmit}
                commitModes={ADD_TO_TESTSET_COMMIT_MODES}
                defaultCommitMode="existing"
                onModeChange={handleAddToTestsetModeChange}
                renderModeContent={renderAddToTestsetModeContent}
                canSubmit={canSubmitAddToTestset}
                createEntityFields={CREATE_TESTSET_FIELDS}
                submitLabel="Add"
                actionLabel="Add to Testset"
            />
        </PageLayout>
    )
}

export default AnnotationSession
