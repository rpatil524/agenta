import {useCallback, useState} from "react"

import {EnhancedModal as Modal} from "@agenta/ui"
import {Button, Form, Input, Select} from "antd"

import {getAgentaApiUrl} from "@/oss/lib/helpers/api"
import type {ConnectionCreateRequest} from "@/oss/services/tools/api/types"

import {useToolsConnections} from "../hooks/useToolsConnections"

interface Props {
    open: boolean
    integrationKey: string
    integrationName: string
    authSchemes: string[]
    noAuth: boolean
    onClose: () => void
}

type AuthMode = "oauth" | "api_key"

function resolveAvailableModes(authSchemes: string[], noAuth: boolean): AuthMode[] {
    const modes: AuthMode[] = []
    if (authSchemes.some((s) => s.toLowerCase().includes("oauth"))) modes.push("oauth")
    if (
        authSchemes.some(
            (s) => s.toLowerCase().includes("api_key") || s.toLowerCase().includes("basic"),
        )
    )
        modes.push("api_key")
    if (modes.length === 0 && !noAuth) modes.push("oauth")
    return modes
}

export default function ConnectModal({
    open,
    integrationKey,
    integrationName,
    authSchemes,
    noAuth,
    onClose,
}: Props) {
    const {handleCreate} = useToolsConnections(integrationKey)
    const [loading, setLoading] = useState(false)
    const [form] = Form.useForm()

    const availableModes = resolveAvailableModes(authSchemes, noAuth)
    const [selectedMode, setSelectedMode] = useState<AuthMode>(availableModes[0] || "oauth")

    const callbackUrl = `${getAgentaApiUrl()}/preview/tools/callback`

    const handleClose = useCallback(() => {
        form.resetFields()
        setLoading(false)
        onClose()
    }, [form, onClose])

    const handleSubmit = useCallback(async () => {
        try {
            const values = await form.validateFields()
            setLoading(true)

            const payload: ConnectionCreateRequest = {
                slug: values.slug,
                name: values.name || values.slug,
                mode: selectedMode,
                ...(selectedMode === "oauth" ? {callback_url: callbackUrl} : {}),
                ...(selectedMode === "api_key" && values.api_key
                    ? {credentials: {api_key: values.api_key}}
                    : {}),
            }

            const result = await handleCreate(payload)

            if (result.redirect_url) {
                // OAuth: open popup window
                const popup = window.open(
                    result.redirect_url,
                    "tools_oauth",
                    "width=600,height=700,popup=yes",
                )

                // Listen for postMessage from callback page
                const handler = (event: MessageEvent) => {
                    if (event.data?.type === "tools:oauth:complete") {
                        window.removeEventListener("message", handler)
                        handleClose()
                    }
                }
                window.addEventListener("message", handler)

                // Fallback: detect popup closed without postMessage
                const pollTimer = setInterval(() => {
                    if (popup && popup.closed) {
                        clearInterval(pollTimer)
                        window.removeEventListener("message", handler)
                        handleClose()
                    }
                }, 1000)
            } else {
                // API key flow: connection created immediately
                handleClose()
            }
        } catch {
            setLoading(false)
        }
    }, [form, selectedMode, handleCreate, callbackUrl, handleClose])

    return (
        <Modal
            open={open}
            onCancel={handleClose}
            title={`Connect to ${integrationName}`}
            footer={[
                <Button key="cancel" onClick={handleClose}>
                    Cancel
                </Button>,
                <Button key="connect" type="primary" loading={loading} onClick={handleSubmit}>
                    {selectedMode === "oauth" ? "Connect via OAuth" : "Connect"}
                </Button>,
            ]}
        >
            <Form form={form} layout="vertical" className="mt-4">
                <Form.Item
                    name="slug"
                    label="Connection Slug"
                    rules={[{required: true, message: "Required"}]}
                    tooltip="A unique identifier for this connection"
                >
                    <Input placeholder="e.g. my-gmail" />
                </Form.Item>

                <Form.Item name="name" label="Display Name">
                    <Input placeholder="e.g. My Gmail Account" />
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
        </Modal>
    )
}
