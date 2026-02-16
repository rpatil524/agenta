import {Tag} from "antd"

import type {ConnectionItem} from "@/oss/services/tools/api/types"

export default function ConnectionStatusBadge({connection}: {connection: ConnectionItem}) {
    if (connection.is_valid && connection.is_active) {
        return <Tag color="success">Connected</Tag>
    }
    if (!connection.is_active) {
        return <Tag color="default">Inactive</Tag>
    }
    if (connection.status?.toLowerCase() === "failed") {
        return <Tag color="error">Failed</Tag>
    }
    return <Tag color="processing">Pending</Tag>
}
