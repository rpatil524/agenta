import axios from "@/oss/lib/api/assets/axiosConfig"
import {getAgentaApiUrl} from "@/oss/lib/helpers/api"

import type {
    ProvidersResponse,
    IntegrationsResponse,
    IntegrationDetailResponse,
    ActionsListResponse,
    ConnectionCreateRequest,
    ConnectionResponse,
    ConnectionsListResponse,
    RefreshResponse,
} from "./types"

//Prefix convention:
//  - fetch: GET single entity from server
//  - fetchAll: GET all entities from server
//  - create: POST data to server
//  - delete: DELETE data from server

const BASE = () => `${getAgentaApiUrl()}/preview/tools`

// --- Catalog browse ---

export const fetchProviders = async (): Promise<ProvidersResponse> => {
    const {data} = await axios.get(`${BASE()}/catalog/providers`)
    return data
}

export const fetchIntegrations = async (
    providerKey: string,
    params?: {search?: string; limit?: number},
): Promise<IntegrationsResponse> => {
    const {data} = await axios.get(`${BASE()}/catalog/providers/${providerKey}/integrations`, {
        params,
    })
    return data
}

export const fetchIntegrationDetail = async (
    providerKey: string,
    integrationKey: string,
): Promise<IntegrationDetailResponse> => {
    const {data} = await axios.get(
        `${BASE()}/catalog/providers/${providerKey}/integrations/${integrationKey}`,
    )
    return data
}

export const fetchActions = async (
    providerKey: string,
    integrationKey: string,
    params?: {limit?: number; important?: boolean},
): Promise<ActionsListResponse> => {
    const {data} = await axios.get(
        `${BASE()}/catalog/providers/${providerKey}/integrations/${integrationKey}/actions`,
        {params},
    )
    return data
}

// --- Connections ---

export const fetchConnections = async (
    providerKey: string,
    integrationKey: string,
): Promise<ConnectionsListResponse> => {
    const {data} = await axios.get(
        `${BASE()}/catalog/providers/${providerKey}/integrations/${integrationKey}/connections`,
    )
    return data
}

export const createConnection = async (
    providerKey: string,
    integrationKey: string,
    payload: ConnectionCreateRequest,
): Promise<ConnectionResponse> => {
    const {data} = await axios.post(
        `${BASE()}/catalog/providers/${providerKey}/integrations/${integrationKey}/connections`,
        payload,
    )
    return data
}

export const deleteToolConnection = async (
    providerKey: string,
    integrationKey: string,
    connectionSlug: string,
): Promise<void> => {
    await axios.delete(
        `${BASE()}/catalog/providers/${providerKey}/integrations/${integrationKey}/connections/${connectionSlug}`,
    )
}

export const refreshToolConnection = async (
    providerKey: string,
    integrationKey: string,
    connectionSlug: string,
): Promise<RefreshResponse> => {
    const {data} = await axios.post(
        `${BASE()}/catalog/providers/${providerKey}/integrations/${integrationKey}/connections/${connectionSlug}/refresh`,
    )
    return data
}
