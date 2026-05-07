export function getAddToTestsetDisabledReason({
    scenarioId,
    isCompleted,
    isSubmitting,
    isExporting,
    hasPendingChanges,
}: {
    scenarioId: string
    isCompleted: boolean
    isSubmitting: boolean
    isExporting: boolean
    hasPendingChanges: boolean
}): string | null {
    if (!scenarioId) return "Select a scenario before adding it to a testset."
    if (hasPendingChanges && !isCompleted) return "Save annotations before adding to a testset."
    if (isSubmitting) return "Saving annotations"
    if (isExporting) return "Exporting testset"
    return null
}
