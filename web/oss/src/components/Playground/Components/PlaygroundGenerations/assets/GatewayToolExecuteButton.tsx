import React, {useCallback, useState} from "react"

import {Lightning} from "@phosphor-icons/react"
import {Button, message as antMessage} from "antd"

import {executeToolCall} from "@/oss/services/tools/api"

// Gateway tool function name format: tools__{provider}__{integration}__{action}__{connection}
// Double-underscore is used because LLM providers forbid dots in function names.
// The /tools/call API normalises __ → . before parsing.
// Segments may contain single underscores (e.g. CREATE_EMAIL_DRAFT); only __ is a separator.
function isGatewaySlug(name: string): boolean {
    const parts = name.split("__")
    return parts.length === 5 && parts[0] === "tools" && parts.slice(1).every(Boolean)
}

export interface GatewayToolPayloadInfo {
    name?: string
    callId?: string
    json: string
}

interface Props {
    toolPayloads: GatewayToolPayloadInfo[]
    onUpdateToolResponse: (callId: string | undefined, resultStr: string) => void
}

const GatewayToolExecuteButton: React.FC<Props> = ({toolPayloads, onUpdateToolResponse}) => {
    const [executingId, setExecutingId] = useState<string | null>(null)

    const handleExecute = useCallback(
        async (p: GatewayToolPayloadInfo) => {
            const execId = p.callId || p.name || "default"
            setExecutingId(execId)

            try {
                const response = await executeToolCall({
                    data: {
                        id: p.callId || "",
                        type: "function",
                        function: {
                            name: p.name!,
                            arguments: p.json, // pass raw JSON string as LLM returned it
                        },
                    },
                })
                const resultStr =
                    response.call?.data?.content ?? JSON.stringify(response.call?.data, null, 2)
                onUpdateToolResponse(p.callId, resultStr)
            } catch {
                antMessage.error("Tool execution failed")
            } finally {
                setExecutingId(null)
            }
        },
        [onUpdateToolResponse],
    )

    const gatewayPayloads = toolPayloads.filter((p) => isGatewaySlug(p.name || ""))
    if (gatewayPayloads.length === 0) return null

    return (
        <div className="flex flex-col gap-1">
            {gatewayPayloads.map((p) => (
                <Button
                    key={p.callId || p.name}
                    size="small"
                    icon={<Lightning size={12} />}
                    loading={executingId === (p.callId || p.name || "default")}
                    onClick={() => handleExecute(p)}
                >
                    Call tool
                </Button>
            ))}
        </div>
    )
}

export default GatewayToolExecuteButton
