import {useAtomValue} from "jotai"
import {atomWithQuery} from "jotai-tanstack-query"

import {fetchIntegrations} from "@/oss/services/tools/api"
import type {IntegrationItem} from "@/oss/services/tools/api/types"

const DEFAULT_PROVIDER = "composio"

export const integrationsQueryAtom = atomWithQuery<{
    count: number
    items: IntegrationItem[]
}>(() => ({
    queryKey: ["tools", "integrations", DEFAULT_PROVIDER],
    queryFn: () => fetchIntegrations(DEFAULT_PROVIDER),
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
}))

export const useToolsIntegrations = () => {
    const query = useAtomValue(integrationsQueryAtom)
    const integrations: IntegrationItem[] = query.data?.items ?? []

    return {
        integrations,
        isLoading: query.isPending,
        error: query.error,
        refetch: query.refetch,
    }
}
