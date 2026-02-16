from typing import List, Optional, Union

from pydantic import BaseModel

from oss.src.core.shared.dtos import Windowing
from oss.src.core.tools.dtos import (
    # Tool Catalog
    ToolCatalogAction,
    ToolCatalogActionDetails,
    ToolCatalogIntegration,
    ToolCatalogIntegrationDetails,
    ToolCatalogProvider,
    ToolCatalogProviderDetails,
    # Tool Connections
    ToolConnection,
    ToolConnectionCreate,
    # Tools
    Tool,
    ToolQuery,
    # Tool Calls
    ToolCall,
    ToolResult,
)


# ---------------------------------------------------------------------------
# Tool Catalog
# ---------------------------------------------------------------------------


class ToolCatalogProviderResponse(BaseModel):
    count: int = 0
    provider: Optional[Union[ToolCatalogProvider, ToolCatalogProviderDetails]] = None


class ToolCatalogProvidersResponse(BaseModel):
    count: int = 0
    providers: List[Union[ToolCatalogProvider, ToolCatalogProviderDetails]] = []


class ToolCatalogIntegrationResponse(BaseModel):
    count: int = 0
    integration: Optional[
        Union[ToolCatalogIntegration, ToolCatalogIntegrationDetails]
    ] = None


class ToolCatalogIntegrationsResponse(BaseModel):
    count: int = 0
    integrations: List[
        Union[ToolCatalogIntegration, ToolCatalogIntegrationDetails]
    ] = []


class ToolCatalogActionResponse(BaseModel):
    count: int = 0
    action: Optional[Union[ToolCatalogAction, ToolCatalogActionDetails]] = None


class ToolCatalogActionsResponse(BaseModel):
    count: int = 0
    actions: List[Union[ToolCatalogAction, ToolCatalogActionDetails]] = []


# ---------------------------------------------------------------------------
# Tool Connections
# ---------------------------------------------------------------------------


class ToolConnectionCreateRequest(BaseModel):
    connection: ToolConnectionCreate


class ToolConnectionResponse(BaseModel):
    count: int = 0
    connection: Optional[ToolConnection] = None


class ToolConnectionsResponse(BaseModel):
    count: int = 0
    connections: List[ToolConnection] = []


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


class ToolQueryRequest(BaseModel):
    tool: Optional[ToolQuery] = None
    #
    windowing: Optional[Windowing] = None


class ToolResponse(BaseModel):
    count: int = 0
    tool: Optional[Tool] = None


class ToolsResponse(BaseModel):
    count: int = 0
    tools: List[Tool] = []


# ---------------------------------------------------------------------------
# Tool Calls
# ---------------------------------------------------------------------------


class ToolCallRequest(BaseModel):
    call: ToolCall


class ToolCallResponse(BaseModel):
    result: ToolResult
