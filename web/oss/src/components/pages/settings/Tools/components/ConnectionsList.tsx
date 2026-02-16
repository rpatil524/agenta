import {useMemo} from "react"

import {ArrowsClockwise, Trash} from "@phosphor-icons/react"
import {Button, Table, Tooltip, Typography} from "antd"
import type {ColumnsType} from "antd/es/table"

import AlertPopup from "@/oss/components/AlertPopup/AlertPopup"
import {formatDay} from "@/oss/lib/helpers/dateTimeHelper"
import type {ConnectionItem} from "@/oss/services/tools/api/types"

import {useToolsConnections} from "../hooks/useToolsConnections"

import ConnectionStatusBadge from "./ConnectionStatusBadge"

interface Props {
    integrationKey: string
    connections: ConnectionItem[]
}

export default function ConnectionsList({integrationKey, connections}: Props) {
    const {handleDelete, handleRefresh} = useToolsConnections(integrationKey)

    const confirmDelete = (slug: string) => {
        AlertPopup({
            title: "Delete Connection",
            message:
                "Are you sure you want to delete this connection? This action is irreversible.",
            onOk: () => handleDelete(slug),
        })
    }

    const columns: ColumnsType<ConnectionItem> = useMemo(
        () => [
            {
                title: "Name",
                dataIndex: "slug",
                key: "slug",
                render: (slug: string, record) => (
                    <Typography.Text>{record.name || slug}</Typography.Text>
                ),
            },
            {
                title: "Status",
                key: "status",
                width: 120,
                render: (_, record) => <ConnectionStatusBadge connection={record} />,
            },
            {
                title: "Created",
                dataIndex: "created_at",
                key: "created_at",
                width: 180,
                render: (value: string) =>
                    value ? formatDay({date: value, outputFormat: "YYYY-MM-DD HH:mm"}) : "-",
            },
            {
                key: "actions",
                width: 80,
                align: "center" as const,
                render: (_, record) => (
                    <div className="flex items-center gap-1">
                        <Tooltip title="Refresh">
                            <Button
                                type="text"
                                size="small"
                                icon={<ArrowsClockwise size={14} />}
                                onClick={() => handleRefresh(record.slug)}
                            />
                        </Tooltip>
                        <Tooltip title="Delete">
                            <Button
                                type="text"
                                size="small"
                                color="danger"
                                variant="text"
                                icon={<Trash size={14} />}
                                onClick={() => confirmDelete(record.slug)}
                            />
                        </Tooltip>
                    </div>
                ),
            },
        ],
        [handleDelete, handleRefresh],
    )

    return (
        <Table<ConnectionItem>
            dataSource={connections}
            columns={columns}
            rowKey="slug"
            pagination={false}
            size="small"
            bordered
            locale={{emptyText: "No connections yet"}}
        />
    )
}
