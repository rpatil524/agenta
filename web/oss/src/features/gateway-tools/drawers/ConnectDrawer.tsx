import {useCallback, useState} from "react"

import {Button, Divider, Drawer, Form, Input, Select, Typography} from "antd"

import {queryClient} from "@/oss/lib/api/queryClient"
import {createConnection, fetchConnection} from "@/oss/services/tools/api"

const DEFAULT_PROVIDER = "composio"

type AuthMode = "oauth" | "api_key"

interface Props {
    open: boolean
    integrationKey: string
    integrationName: string
    integrationLogo?: string
    integrationDescription?: string
    authSchemes: string[]
    onClose: () => void
    onSuccess?: () => void
}

function resolveAvailableModes(authSchemes: string[]): AuthMode[] {
    const modes: AuthMode[] = []
    if (authSchemes.some((s) => s.toLowerCase().includes("oauth"))) modes.push("oauth")
    if (
        authSchemes.some(
            (s) => s.toLowerCase().includes("api_key") || s.toLowerCase().includes("basic"),
        )
    )
        modes.push("api_key")
    if (modes.length === 0) modes.push("oauth")
    return modes
}

export default function ConnectDrawer({
    open,
    integrationKey,
    integrationName,
    integrationLogo,
    integrationDescription,
    authSchemes,
    onClose,
    onSuccess,
}: Props) {
    const [loading, setLoading] = useState(false)
    const [form] = Form.useForm()

    const availableModes = resolveAvailableModes(authSchemes)
    const [selectedMode, setSelectedMode] = useState<AuthMode>(availableModes[0] || "oauth")

    const handleClose = useCallback(() => {
        form.resetFields()
        setLoading(false)
        onClose()
    }, [form, onClose])

    const invalidateConnections = useCallback(() => {
        queryClient.invalidateQueries({queryKey: ["tools", "connections"]})
        queryClient.invalidateQueries({queryKey: ["tools", "catalog"]})
    }, [])

    const handleSubmit = useCallback(async () => {
        try {
            const values = await form.validateFields()
            setLoading(true)

            const result = await createConnection({
                connection: {
                    slug: values.slug,
                    name: values.name || values.slug,
                    provider_key: DEFAULT_PROVIDER,
                    integration_key: integrationKey,
                    data: {
                        auth_scheme: selectedMode,
                        ...(selectedMode === "api_key" && values.api_key
                            ? {credentials: {api_key: values.api_key}}
                            : {}),
                    },
                },
            })

            invalidateConnections()

            const redirectUrl = (result.connection?.data as Record<string, unknown> | undefined)
                ?.redirect_url
            if (redirectUrl) {
                // OAuth: open popup window
                const popup = window.open(
                    redirectUrl,
                    "tools_oauth",
                    "width=600,height=700,popup=yes",
                )

                const connectionId = result.connection?.id

                const onOAuthDone = async () => {
                    // Poll the individual connection endpoint which checks
                    // Composio for status and updates is_valid in the DB.
                    if (connectionId) {
                        try {
                            await fetchConnection(connectionId)
                        } catch {
                            /* best-effort */
                        }
                    }
                    invalidateConnections()
                    handleClose()
                    onSuccess?.()
                }

                const handler = (event: MessageEvent) => {
                    if (event.data?.type === "tools:oauth:complete") {
                        window.removeEventListener("message", handler)
                        onOAuthDone()
                    }
                }
                window.addEventListener("message", handler)

                // Fallback: detect popup closed
                const pollTimer = setInterval(() => {
                    if (popup && popup.closed) {
                        clearInterval(pollTimer)
                        window.removeEventListener("message", handler)
                        onOAuthDone()
                    }
                }, 1000)
            } else {
                // API key or no-auth: connection created immediately
                handleClose()
                onSuccess?.()
            }
        } catch {
            setLoading(false)
        }
    }, [form, selectedMode, integrationKey, handleClose, onSuccess, invalidateConnections])

    return (
        <Drawer
            open={open}
            onClose={handleClose}
            title={`Connect to ${integrationName}`}
            width={420}
            footer={
                <div className="flex justify-end gap-2">
                    <Button onClick={handleClose}>Cancel</Button>
                    <Button type="primary" loading={loading} onClick={handleSubmit}>
                        {selectedMode === "oauth" ? "Connect via OAuth" : "Connect"}
                    </Button>
                </div>
            }
        >
            <div className="flex items-start gap-3">
                {integrationLogo && (
                    <img
                        src={integrationLogo}
                        alt={integrationName}
                        className="w-10 h-10 rounded object-contain shrink-0"
                    />
                )}
                <div className="flex flex-col min-w-0">
                    <Typography.Text strong>{integrationName}</Typography.Text>
                    {integrationDescription && (
                        <Typography.Paragraph
                            type="secondary"
                            className="!text-xs !mb-0"
                            ellipsis={{
                                rows: 3,
                                expandable: "collapsible",
                                symbol: (expanded: boolean) => (expanded ? "see less" : "see more"),
                            }}
                        >
                            {integrationDescription}
                        </Typography.Paragraph>
                    )}
                </div>
            </div>

            <Divider className="!my-4" />

            <Form form={form} layout="vertical">
                <Form.Item
                    name="slug"
                    label="Connection Slug"
                    rules={[{required: true, message: "Required"}]}
                    tooltip="A unique identifier for this connection"
                >
                    <Input placeholder={`e.g. my-${integrationKey}`} />
                </Form.Item>

                <Form.Item name="name" label="Display Name">
                    <Input placeholder={`e.g. My ${integrationName} Account`} />
                </Form.Item>

                {availableModes.length > 1 && (
                    <Form.Item label="Auth Method">
                        <Select
                            value={selectedMode}
                            onChange={setSelectedMode}
                            options={availableModes.map((m) => ({
                                value: m,
                                label: m === "oauth" ? "OAuth" : "API Key",
                            }))}
                        />
                    </Form.Item>
                )}

                {selectedMode === "api_key" && (
                    <Form.Item
                        name="api_key"
                        label="API Key"
                        rules={[{required: true, message: "API key is required"}]}
                    >
                        <Input.Password placeholder="Enter API key" />
                    </Form.Item>
                )}
            </Form>
        </Drawer>
    )
}
