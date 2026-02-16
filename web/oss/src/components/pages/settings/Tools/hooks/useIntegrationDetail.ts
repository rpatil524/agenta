import {useAtomValue} from "jotai"
import {atomFamily} from "jotai/utils"
import {atomWithQuery} from "jotai-tanstack-query"

import {fetchIntegrationDetail, fetchActions} from "@/oss/services/tools/api"
import type {IntegrationDetailResponse, ActionsListResponse} from "@/oss/services/tools/api/types"

const DEFAULT_PROVIDER = "composio"

export const integrationDetailQueryFamily = atomFamily((integrationKey: string) =>
    atomWithQuery<IntegrationDetailResponse>(() => ({
        queryKey: ["tools", "integrationDetail", DEFAULT_PROVIDER, integrationKey],
        queryFn: () => fetchIntegrationDetail(DEFAULT_PROVIDER, integrationKey),
        staleTime: 60_000,
        refetchOnWindowFocus: false,
        enabled: !!integrationKey,
    })),
)

export const integrationActionsQueryFamily = atomFamily((integrationKey: string) =>
    atomWithQuery<ActionsListResponse>(() => ({
        queryKey: ["tools", "actions", DEFAULT_PROVIDER, integrationKey],
        queryFn: () => fetchActions(DEFAULT_PROVIDER, integrationKey, {important: true}),
        staleTime: 5 * 60_000,
        refetchOnWindowFocus: false,
        enabled: !!integrationKey,
    })),
)

export const useIntegrationDetail = (integrationKey: string) => {
    const detailQuery = useAtomValue(integrationDetailQueryFamily(integrationKey))
    const actionsQuery = useAtomValue(integrationActionsQueryFamily(integrationKey))

    return {
        integration: detailQuery.data ?? null,
        connections: detailQuery.data?.connections ?? [],
        actions: actionsQuery.data?.items ?? [],
        isLoading: detailQuery.isPending || actionsQuery.isPending,
        error: detailQuery.error || actionsQuery.error,
        refetchDetail: detailQuery.refetch,
    }
}
