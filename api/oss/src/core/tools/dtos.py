from enum import Enum
from typing import Any, Dict, List, Optional

from agenta.sdk.models.workflows import JsonSchemas
from pydantic import BaseModel

from oss.src.core.shared.dtos import (
    Header,
    Identifier,
    Lifecycle,
    Metadata,
    Slug,
    Json,
)

# ---------------------------------------------------------------------------
# Tool Enums
# ---------------------------------------------------------------------------


class ToolProviderKind(str, Enum):
    COMPOSIO = "composio"
    AGENTA = "agenta"


class ToolAuthScheme(str, Enum):
    OAUTH = "oauth"
    API_KEY = "api_key"


# ---------------------------------------------------------------------------
# Tool Catalog
# ---------------------------------------------------------------------------

# Tags type for filtering tools by tag flags (e.g. {"important": true})
Tags = Optional[Dict[str, bool]]


class ToolCatalogAction(BaseModel):
    key: str
    #
    name: str
    description: Optional[str] = None
    #
    categories: List[str] = []
    logo: Optional[str] = None


class ToolCatalogActionDetails(ToolCatalogAction):
    schemas: Optional[JsonSchemas] = None
    scopes: Optional[List[str]] = None


class ToolCatalogIntegration(BaseModel):
    key: str
    #
    name: str
    description: Optional[str] = None
    #
    categories: List[str] = []
    logo: Optional[str] = None
    url: Optional[str] = None
    #
    actions_count: Optional[int] = None
    #
    auth_schemes: Optional[List[ToolAuthScheme]] = None


class ToolCatalogIntegrationDetails(ToolCatalogIntegration):
    actions: Optional[List[ToolCatalogAction]] = None


class ToolCatalogProvider(BaseModel):
    key: ToolProviderKind
    #
    name: str
    description: Optional[str] = None
    #
    integrations_count: Optional[int] = None
    #


class ToolCatalogProviderDetails(ToolCatalogProvider):
    integrations: Optional[List[ToolCatalogIntegration]] = None


# ---------------------------------------------------------------------------
# Tool Connections
# ---------------------------------------------------------------------------


class ToolConnectionStatus(BaseModel):
    redirect_url: Optional[str] = None


class ToolConnectionCreateData(BaseModel):
    callback_url: Optional[str] = None
    #
    auth_scheme: Optional[ToolAuthScheme] = None
    credentials: Optional[Dict[str, str]] = None


class ToolConnection(
    Identifier,
    Slug,
    Header,
    Lifecycle,
    Metadata,
):
    provider_key: ToolProviderKind
    integration_key: str
    #
    data: Optional[Json] = None
    #
    status: Optional[ToolConnectionStatus] = None

    @property
    def provider_connection_id(self) -> Optional[str]:
        """Get provider-specific connection ID from data."""
        if self.data and isinstance(self.data, dict):
            # For Composio, it's stored as "connected_account_id"
            return self.data.get("connected_account_id") or self.data.get(
                "provider_connection_id"
            )
        return None

    @property
    def is_active(self) -> bool:
        """Check if connection is active (not deleted)."""
        if self.flags and isinstance(self.flags, dict):
            return self.flags.get("is_active", False)
        return False

    @property
    def is_valid(self) -> bool:
        """Check if connection is valid (authenticated)."""
        if self.flags and isinstance(self.flags, dict):
            return self.flags.get("is_valid", False)
        return False


class ToolConnectionCreate(
    Slug,
    Header,
    Metadata,
):
    provider_key: ToolProviderKind
    integration_key: str
    #
    data: Optional[Json] = None


# ---------------------------------------------------------------------------
# Tool Calls
# ---------------------------------------------------------------------------


class ToolCall(Identifier):
    name: str  # ~ tool.slug
    arguments: Dict[str, Any]


class ToolResult(Identifier):
    result: Optional[Json] = None
    status: Optional[Json] = (
        None  # {"message": "success"} or {"message": "failed", "error": "..."}
    )


# ---------------------------------------------------------------------------
# Tool Execution
# ---------------------------------------------------------------------------


class ExecutionResult(BaseModel):
    """Result from executing a tool action via a provider adapter."""

    data: Optional[Json] = None
    error: Optional[str] = None
    successful: bool = False
