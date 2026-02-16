import {useCallback} from "react"

import {queryClient} from "@/oss/lib/api/queryClient"
import {
    createConnection,
    deleteToolConnection,
    refreshToolConnection,
} from "@/oss/services/tools/api"
import type {ConnectionCreateRequest} from "@/oss/services/tools/api/types"

const DEFAULT_PROVIDER = "composio"

export const useToolsConnections = (integrationKey: string) => {
    const invalidate = useCallback(() => {
        queryClient.invalidateQueries({
            queryKey: ["tools", "integrationDetail", DEFAULT_PROVIDER, integrationKey],
        })
        queryClient.invalidateQueries({
            queryKey: ["tools", "integrations"],
        })
    }, [integrationKey])

    const handleCreate = useCallback(
        async (payload: ConnectionCreateRequest) => {
            const result = await createConnection(DEFAULT_PROVIDER, integrationKey, payload)
            invalidate()
            return result
        },
        [integrationKey, invalidate],
    )

    const handleDelete = useCallback(
        async (connectionSlug: string) => {
            await deleteToolConnection(DEFAULT_PROVIDER, integrationKey, connectionSlug)
            invalidate()
        },
        [integrationKey, invalidate],
    )

    const handleRefresh = useCallback(
        async (connectionSlug: string) => {
            const result = await refreshToolConnection(
                DEFAULT_PROVIDER,
                integrationKey,
                connectionSlug,
            )
            invalidate()
            return result
        },
        [integrationKey, invalidate],
    )

    return {handleCreate, handleDelete, handleRefresh}
}
