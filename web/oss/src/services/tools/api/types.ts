// TypeScript interfaces mirroring api/oss/src/apis/fastapi/tools/models.py

// ---------------------------------------------------------------------------
// Catalog browse
// ---------------------------------------------------------------------------

export interface ProviderItem {
    key: string
    name: string
    description?: string
    integrations_count: number
    enabled: boolean
}

export interface ProvidersResponse {
    count: number
    items: ProviderItem[]
}

export interface IntegrationItem {
    key: string
    name: string
    description?: string
    logo?: string
    auth_schemes: string[]
    actions_count: number
    categories: string[]
    no_auth: boolean
    connections_count: number
}

export interface IntegrationsResponse {
    count: number
    items: IntegrationItem[]
}

export interface ConnectionItem {
    slug: string
    name?: string
    description?: string
    is_active: boolean
    is_valid: boolean
    status?: string
    created_at?: string
    updated_at?: string
}

export interface IntegrationDetailResponse {
    key: string
    name: string
    description?: string
    logo?: string
    auth_schemes: string[]
    actions_count: number
    categories: string[]
    no_auth: boolean
    connections: ConnectionItem[]
}

export interface ActionItem {
    key: string
    slug: string
    name: string
    description?: string
    tags?: Record<string, unknown>
}

export interface ActionsListResponse {
    count: number
    items: ActionItem[]
}

// ---------------------------------------------------------------------------
// Connection CRUD
// ---------------------------------------------------------------------------

export interface ConnectionCreateRequest {
    slug: string
    name?: string
    description?: string
    mode: "oauth" | "api_key"
    callback_url?: string
    credentials?: Record<string, string>
}

export interface ConnectionResponse {
    connection: ConnectionItem
    redirect_url?: string
}

export interface ConnectionsListResponse {
    count: number
    connections: ConnectionItem[]
}

export interface RefreshResponse {
    connection: ConnectionItem
    redirect_url?: string
}
