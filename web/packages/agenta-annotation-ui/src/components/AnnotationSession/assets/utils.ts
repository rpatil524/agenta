export function getAddToTestsetDisabledReason({
    scenarioId,
    isSubmitting,
    isExporting,
    hasPendingChanges,
}: {
    scenarioId: string
    isSubmitting: boolean
    isExporting: boolean
    hasPendingChanges: boolean
}): string | null {
    if (!scenarioId) return "Select a scenario before adding it to a testset."
    if (hasPendingChanges) return "Save annotations before adding to a testset."
    if (isSubmitting) return "Saving annotations"
    if (isExporting) return "Exporting testset"
    return null
}
