import {useAtomValue} from "jotai"
import {atomFamily} from "jotai/utils"
import {atomWithQuery} from "jotai-tanstack-query"

import {fetchConnection} from "@/oss/services/tools/api"
import type {ConnectionResponse} from "@/oss/services/tools/api/types"

export const connectionQueryAtomFamily = atomFamily((connectionId: string) =>
    atomWithQuery<ConnectionResponse>(() => ({
        queryKey: ["tools", "connections", connectionId],
        queryFn: () => fetchConnection(connectionId),
        enabled: !!connectionId,
        staleTime: 30_000,
        refetchOnWindowFocus: false,
    })),
)

export const useConnectionQuery = (connectionId?: string) => {
    const query = useAtomValue(connectionQueryAtomFamily(connectionId ?? ""))

    return {
        connection: query.data?.connection ?? null,
        isLoading: !!connectionId && query.isPending,
        error: query.error,
        refetch: query.refetch,
    }
}
