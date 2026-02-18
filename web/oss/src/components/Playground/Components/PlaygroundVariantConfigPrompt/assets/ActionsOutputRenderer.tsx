import React, {useCallback, useMemo, useRef, useState} from "react"

import {CaretRight, MagnifyingGlass, Plus} from "@phosphor-icons/react"
import {Button, Divider, Dropdown, Input, Spin, Tooltip, Typography} from "antd"
import clsx from "clsx"
import {useSetAtom} from "jotai"

import LLMIconMap from "@/oss/components/LLMIcons"
import {getPromptById, getLLMConfig} from "@/oss/components/Playground/context/promptShape"
import {usePromptsSource} from "@/oss/components/Playground/context/PromptsSource"
import {
    catalogDrawerOpenAtom,
    useCatalogActions,
    useConnectionsQuery,
    useIntegrationDetail,
} from "@/oss/features/gateway-tools"
import CatalogDrawer from "@/oss/features/gateway-tools/drawers/CatalogDrawer"
import ToolExecutionDrawer from "@/oss/features/gateway-tools/drawers/ToolExecutionDrawer"
import type {ConnectionItem} from "@/oss/services/tools/api/types"

import AddButton from "../../../assets/AddButton"
import {
    addPromptMessageMutationAtomFamily,
    addPromptToolMutationAtomFamily,
} from "../../../state/atoms/promptMutations"
import {TOOL_PROVIDERS_META} from "../../PlaygroundTool/assets"
import PlaygroundVariantPropertyControl from "../../PlaygroundVariantPropertyControl"

import TemplateFormatSelector from "./TemplateFormatSelector"
import toolsSpecs from "./tools.specs.json"

interface Props {
    variantId: string
    compoundKey: string
    viewOnly?: boolean
}

const formatToolLabel = (toolCode: string) =>
    toolCode
        .split("_")
        .filter(Boolean)
        .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
        .join(" ")

// Right panel: actions for a Composio integration (lazy-fetched)
function ComposioActionsList({
    integrationKey,
    onSelectAction,
}: {
    integrationKey: string
    connections: ConnectionItem[]
    onSelectAction: (actionKey: string, actionName: string) => void
}) {
    const {actions, isLoading} = useCatalogActions(integrationKey)

    if (isLoading) {
        return (
            <div className="flex justify-center py-4">
                <Spin size="small" />
            </div>
        )
    }

    if (!actions.length) {
        return <div className="py-3 px-2 text-[11px] text-[#7E8B99]">No actions found</div>
    }

    return (
        <>
            {actions.map((action) => (
                <Button
                    key={action.key}
                    type="text"
                    block
                    className="!flex !h-[28px] !items-center !justify-start !text-left !py-[5px] !px-2 hover:!bg-[#F8FAFC]"
                    onClick={() => onSelectAction(action.key, action.name)}
                >
                    <span className="text-[#0F172A] text-xs truncate">{action.name}</span>
                </Button>
            ))}
        </>
    )
}

// Left panel row for a Composio integration — fetches its own logo
function IntegrationRow({
    integrationKey,
    count,
    isHovered,
    onHover,
}: {
    integrationKey: string
    count: number
    isHovered: boolean
    onHover: () => void
}) {
    const {integration} = useIntegrationDetail(integrationKey)

    return (
        <Button
            type="text"
            block
            onMouseEnter={onHover}
            className={clsx(
                "!flex !h-[28px] !items-center !gap-1.5 !py-[5px] !px-1.5 !text-left",
                isHovered ? "!bg-[#EFF6FF]" : "hover:!bg-[#F8FAFC]",
            )}
        >
            {integration?.logo ? (
                <img
                    src={integration.logo}
                    alt={integrationKey}
                    className="h-4 w-4 rounded object-contain shrink-0"
                />
            ) : (
                <span className="h-4 w-4 rounded bg-[#F1F5F9] shrink-0" />
            )}
            <Typography.Text className="flex-1 text-[#0F172A] text-xs capitalize truncate">
                {integrationKey.replace(/_/g, " ")}
            </Typography.Text>
            <span className="text-[#94A3B8] text-[10px] shrink-0">{count}</span>
            <CaretRight size={10} className="text-[#CBD5E1] shrink-0" />
        </Button>
    )
}

const ActionsOutputRenderer: React.FC<Props> = ({variantId, compoundKey, viewOnly}) => {
    const addNewMessage = useSetAtom(addPromptMessageMutationAtomFamily(compoundKey))
    const addNewTool = useSetAtom(addPromptToolMutationAtomFamily(compoundKey))
    const [isDropdownOpen, setIsDropdownOpen] = useState(false)
    const [searchTerm, setSearchTerm] = useState("")
    const [hoveredKey, setHoveredKey] = useState<string | null>(null)
    const [leftPanelHeight, setLeftPanelHeight] = useState<number | undefined>(undefined)
    const leftPanelRef = useRef<HTMLDivElement>(null)

    const handleRowHover = useCallback((key: string) => {
        if (leftPanelRef.current) {
            setLeftPanelHeight(leftPanelRef.current.offsetHeight)
        }
        setHoveredKey(key)
    }, [])
    // promptId may contain colons (e.g. "prompt:prompt1"), so split only on the first ":"
    const promptId = compoundKey.substring(compoundKey.indexOf(":") + 1)
    const prompts = usePromptsSource(variantId)

    const setCatalogOpen = useSetAtom(catalogDrawerOpenAtom)
    const {
        connections,
        isLoading: connectionsLoading,
        refetch: refetchConnections,
    } = useConnectionsQuery()

    const responseFormatInfo = useMemo(() => {
        const item = getPromptById(prompts, promptId)
        const llm = getLLMConfig(item)
        const enhancedId = llm?.responseFormat?.__id || llm?.response_format?.__id
        const raw = llm?.response_format || llm?.responseFormat

        return {enhancedId, raw}
    }, [prompts, promptId])
    const responseFormatId = responseFormatInfo.enhancedId as string | undefined

    const filteredToolGroups = useMemo(() => {
        const normalizedTerm = searchTerm.trim().toLowerCase()

        return Object.entries(toolsSpecs).reduce<
            {
                key: string
                label: string
                Icon?: React.FC<{className?: string}>
                tools: {code: string; label: string; payload: Record<string, any>}[]
            }[]
        >((groups, [providerKey, tools]) => {
            const meta = TOOL_PROVIDERS_META[providerKey] ?? {label: providerKey}
            const Icon = meta.iconKey ? LLMIconMap[meta.iconKey] : undefined
            const providerMatches =
                normalizedTerm && meta.label.toLowerCase().includes(normalizedTerm)

            const toolEntries = Object.entries(tools).map(([toolCode, toolSpec]) => ({
                code: toolCode,
                label: formatToolLabel(toolCode),
                payload: Array.isArray(toolSpec) ? toolSpec[0] : toolSpec,
            }))

            const matchingTools = toolEntries.filter((tool) => {
                if (!normalizedTerm) return true
                return (
                    providerMatches ||
                    tool.label.toLowerCase().includes(normalizedTerm) ||
                    tool.code.toLowerCase().includes(normalizedTerm)
                )
            })

            if (matchingTools.length) {
                groups.push({key: providerKey, label: meta.label, Icon, tools: matchingTools})
            }

            return groups
        }, [])
    }, [searchTerm])

    // Group connections by integration, filtered by search term
    const groupedConnections = useMemo(() => {
        const normalizedTerm = searchTerm.trim().toLowerCase()
        const map: Record<string, ConnectionItem[]> = {}
        for (const conn of connections) {
            const key = conn.integration_key
            if (
                normalizedTerm &&
                !key.toLowerCase().includes(normalizedTerm) &&
                !(conn.name || conn.slug).toLowerCase().includes(normalizedTerm)
            ) {
                continue
            }
            if (!map[key]) map[key] = []
            map[key].push(conn)
        }
        return map
    }, [connections, searchTerm])

    const integrationKeys = Object.keys(groupedConnections)
    const hasBuiltin = filteredToolGroups.length > 0
    const hasComposio = connectionsLoading || integrationKeys.length > 0

    const closeDropdown = useCallback(() => {
        setIsDropdownOpen(false)
        setSearchTerm("")
        setHoveredKey(null)
    }, [])

    const handleAddTool = useCallback(
        (params?: {
            payload?: Record<string, any>
            source?: "inline" | "builtin"
            providerKey?: string
            providerLabel?: string
            toolCode?: string
            toolLabel?: string
        }) => {
            addNewTool(params)
            closeDropdown()
        },
        [addNewTool, closeDropdown],
    )

    const handleComposioActionAdd = useCallback(
        (integrationKey: string, actionKey: string, actionName: string) => {
            addNewTool({
                source: "builtin",
                providerKey: `composio.${integrationKey}`,
                providerLabel: "Composio",
                toolCode: actionKey,
                toolLabel: actionName,
            })
            closeDropdown()
        },
        [addNewTool, closeDropdown],
    )

    // Derive right-panel content from hoveredKey
    const hoveredBuiltinGroup = hoveredKey?.startsWith("builtin:")
        ? filteredToolGroups.find((g) => g.key === hoveredKey.slice("builtin:".length))
        : null
    const hoveredIntegrationKey = hoveredKey?.startsWith("composio:")
        ? hoveredKey.slice("composio:".length)
        : null
    const showRightPanel = !!(hoveredBuiltinGroup || hoveredIntegrationKey)

    const dropdownContent = (
        <div
            className="flex items-start bg-white rounded-lg shadow-lg overflow-hidden"
            onMouseLeave={() => setHoveredKey(null)}
        >
            {/* Left panel */}
            <div ref={leftPanelRef} className="w-[220px] flex flex-col shrink-0">
                <div className="flex items-center gap-2 p-2">
                    <Input
                        allowClear
                        autoFocus
                        variant="borderless"
                        placeholder="Search"
                        value={searchTerm}
                        onChange={(event) => {
                            setSearchTerm(event.target.value)
                            setHoveredKey(null)
                        }}
                        prefix={<MagnifyingGlass size={16} className="text-[#98A2B3]" />}
                        className="flex-1 !shadow-none !outline-none !border-none focus:!shadow-none focus:!outline-none focus:!border-none"
                    />
                    <Button
                        type="primary"
                        size="small"
                        className="shrink-0"
                        onClick={() => handleAddTool({source: "inline"})}
                    >
                        + Create in-line
                    </Button>
                </div>

                <Divider className="m-0" orientation="horizontal" />

                <div className="max-h-80 overflow-y-auto flex flex-col p-1">
                    {/* Builtin section */}
                    {hasBuiltin && (
                        <div className="flex flex-col">
                            <Typography.Text className="text-[#758391] text-xs py-[5px] px-1.5 font-medium">
                                Builtin
                            </Typography.Text>
                            {filteredToolGroups.map(({key, label, Icon}) => (
                                <Button
                                    key={key}
                                    type="text"
                                    block
                                    onMouseEnter={() => handleRowHover(`builtin:${key}`)}
                                    className={clsx(
                                        "!flex !h-[28px] !items-center !gap-1.5 !py-[5px] !px-1.5 !text-left",
                                        hoveredKey === `builtin:${key}`
                                            ? "!bg-[#EFF6FF]"
                                            : "hover:!bg-[#F8FAFC]",
                                    )}
                                >
                                    {Icon ? (
                                        <span className="flex h-5 w-5 items-center justify-center overflow-hidden rounded-full bg-[#F8FAFC] shrink-0">
                                            <Icon className="h-3.5 w-3.5 text-[#758391]" />
                                        </span>
                                    ) : (
                                        <span className="h-5 w-5 shrink-0" />
                                    )}
                                    <Typography.Text className="flex-1 text-[#0F172A] text-xs">
                                        {label}
                                    </Typography.Text>
                                    <CaretRight size={10} className="text-[#CBD5E1] shrink-0" />
                                </Button>
                            ))}
                        </div>
                    )}

                    {/* Composio section */}
                    {hasComposio && (
                        <>
                            {hasBuiltin && <Divider className="my-1" orientation="horizontal" />}
                            <div className="flex items-center justify-between py-[5px] px-1.5">
                                <Typography.Text className="text-[#758391] text-xs font-medium">
                                    Composio
                                </Typography.Text>
                                <Tooltip title="Add integration">
                                    <Button
                                        type="text"
                                        size="small"
                                        icon={<Plus size={12} />}
                                        className="h-5 w-5 flex items-center justify-center p-0 text-[#758391]"
                                        onClick={(e) => {
                                            e.stopPropagation()
                                            setIsDropdownOpen(false)
                                            setCatalogOpen(true)
                                        }}
                                    />
                                </Tooltip>
                            </div>
                            {connectionsLoading ? (
                                <div className="flex justify-center py-2">
                                    <Spin size="small" />
                                </div>
                            ) : (
                                integrationKeys.map((key) => (
                                    <IntegrationRow
                                        key={key}
                                        integrationKey={key}
                                        count={groupedConnections[key].length}
                                        isHovered={hoveredKey === `composio:${key}`}
                                        onHover={() => handleRowHover(`composio:${key}`)}
                                    />
                                ))
                            )}
                        </>
                    )}

                    {/* Empty state */}
                    {!hasBuiltin && !hasComposio && (
                        <div className="py-8 text-center text-[12px] leading-5 text-[#7E8B99]">
                            No tools found
                        </div>
                    )}
                </div>
            </div>

            {/* Right panel: actions on hover — height locked to left panel */}
            {showRightPanel && (
                <div
                    className="w-[220px] overflow-y-auto flex flex-col p-1 shrink-0 border-l border-[#F0F0F0]"
                    style={leftPanelHeight ? {height: leftPanelHeight} : undefined}
                >
                    {hoveredBuiltinGroup &&
                        hoveredBuiltinGroup.tools.map(({code, label: toolLabel, payload}) => (
                            <Button
                                key={code}
                                type="text"
                                block
                                className="!flex !h-[28px] !items-center !justify-start !text-left !py-[5px] !px-2 hover:!bg-[#F8FAFC]"
                                onClick={() =>
                                    handleAddTool({
                                        payload,
                                        source: "builtin",
                                        providerKey: hoveredBuiltinGroup.key,
                                        providerLabel: hoveredBuiltinGroup.label,
                                        toolCode: code,
                                        toolLabel,
                                    })
                                }
                            >
                                <span className="text-[#0F172A] text-xs">{toolLabel}</span>
                            </Button>
                        ))}

                    {hoveredIntegrationKey && (
                        <ComposioActionsList
                            integrationKey={hoveredIntegrationKey}
                            connections={groupedConnections[hoveredIntegrationKey] || []}
                            onSelectAction={(actionKey, actionName) =>
                                handleComposioActionAdd(
                                    hoveredIntegrationKey,
                                    actionKey,
                                    actionName,
                                )
                            }
                        />
                    )}
                </div>
            )}
        </div>
    )

    return (
        <div
            className={clsx(["flex gap-1 flex-wrap w-full", "mb-6"], {
                "[&>_div]:!w-full": viewOnly,
            })}
        >
            {!viewOnly && (
                <>
                    <AddButton
                        className="mt-2"
                        size="small"
                        label="Message"
                        onClick={addNewMessage}
                    />
                    <Dropdown
                        open={isDropdownOpen}
                        onOpenChange={(open) => {
                            setIsDropdownOpen(open)
                            if (!open) {
                                setSearchTerm("")
                                setHoveredKey(null)
                            }
                        }}
                        trigger={["click"]}
                        menu={{items: []}}
                        popupRender={() => dropdownContent}
                        placement="bottomLeft"
                    >
                        <AddButton
                            className="mt-2"
                            size="small"
                            label="Tool"
                            onClick={() => setIsDropdownOpen(true)}
                        />
                    </Dropdown>
                </>
            )}
            <div>
                {responseFormatId ? (
                    <PlaygroundVariantPropertyControl
                        variantId={variantId}
                        propertyId={responseFormatId}
                        viewOnly={viewOnly}
                        disabled={viewOnly}
                        className="!min-h-0 [&_div]:!mb-0"
                    />
                ) : (
                    // Fallback for immutable/raw params (no property id)
                    <span className="text-[#7E8B99] text-[12px] leading-[20px] block">
                        {(() => {
                            const t = (responseFormatInfo.raw || {})?.type
                            if (!t || t === "text") return "Default (text)"
                            if (t === "json_object") return "JSON mode"
                            if (t === "json_schema") return "JSON schema"
                            return String(t)
                        })()}
                    </span>
                )}
            </div>
            <TemplateFormatSelector variantId={variantId} disabled={viewOnly} />

            <CatalogDrawer onConnectionCreated={refetchConnections} />
            <ToolExecutionDrawer />
        </div>
    )
}

export default ActionsOutputRenderer
