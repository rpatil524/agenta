from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from oss.src.utils.logging import get_module_logger
from oss.src.utils.env import env

from oss.src.core.tools.dtos import (
    ToolCatalogAction,
    ToolCatalogActionDetails,
    ToolCatalogIntegration,
    ToolCatalogProvider,
    ToolConnection,
    ToolConnectionCreate,
    Tags,
)
from oss.src.core.tools.interfaces import (
    ToolsDAOInterface,
)
from oss.src.core.tools.registry import GatewayAdapterRegistry
from oss.src.core.tools.exceptions import (
    ConnectionInactiveError,
    ConnectionNotFoundError,
)


log = get_module_logger(__name__)


class ToolsService:
    def __init__(
        self,
        *,
        tools_dao: ToolsDAOInterface,
        adapter_registry: GatewayAdapterRegistry,
    ):
        self.tools_dao = tools_dao
        self.adapter_registry = adapter_registry

    # -----------------------------------------------------------------------
    # Catalog browse
    # -----------------------------------------------------------------------

    async def list_providers(self) -> List[ToolCatalogProvider]:
        results: List[ToolCatalogProvider] = []
        for _key, adapter in self.adapter_registry.items():
            providers = await adapter.list_providers()
            results.extend(providers)
        return results

    async def get_provider(
        self,
        *,
        provider_key: str,
    ) -> Optional[ToolCatalogProvider]:
        adapter = self.adapter_registry.get(provider_key)
        providers = await adapter.list_providers()
        for p in providers:
            if p.key == provider_key:
                return p
        return None

    async def list_integrations(
        self,
        *,
        provider_key: str,
        #
        search: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> Tuple[List[ToolCatalogIntegration], Optional[str], int]:
        adapter = self.adapter_registry.get(provider_key)
        integrations, next_cursor, total = await adapter.list_integrations(
            search=search,
            limit=limit,
            cursor=cursor,
        )
        return integrations, next_cursor, total

    async def get_integration(
        self,
        *,
        provider_key: str,
        integration_key: str,
    ) -> Optional[ToolCatalogIntegration]:
        adapter = self.adapter_registry.get(provider_key)
        # Fetch with max limit to find the specific integration
        integrations, _, _ = await adapter.list_integrations(limit=1000)
        target = None
        for i in integrations:
            if i.key == integration_key:
                target = i
                break

        return target

    async def list_actions(
        self,
        *,
        provider_key: str,
        integration_key: str,
        #
        search: Optional[str] = None,
        tags: Optional[Tags] = None,
        important: Optional[bool] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> Tuple[List[ToolCatalogAction], Optional[str], int]:
        adapter = self.adapter_registry.get(provider_key)
        return await adapter.list_actions(
            integration_key=integration_key,
            search=search,
            tags=tags,
            important=important,
            limit=limit,
            cursor=cursor,
        )

    async def get_action(
        self,
        *,
        provider_key: str,
        integration_key: str,
        action_key: str,
    ) -> Optional[ToolCatalogActionDetails]:
        adapter = self.adapter_registry.get(provider_key)
        return await adapter.get_action(
            integration_key=integration_key,
            action_key=action_key,
        )

    # -----------------------------------------------------------------------
    # Connection management
    # -----------------------------------------------------------------------

    async def query_connections(
        self,
        *,
        project_id: UUID,
        #
        provider_key: Optional[str] = None,
        integration_key: Optional[str] = None,
    ) -> List[ToolConnection]:
        """Query connections with optional filtering."""
        return await self.tools_dao.query_connections(
            project_id=project_id,
            provider_key=provider_key,
            integration_key=integration_key,
        )

    async def find_connection_by_provider_connection_id(
        self,
        *,
        provider_connection_id: str,
    ) -> Optional[ToolConnection]:
        """Find any connection by its provider-side ID (for OAuth callbacks)."""
        return await self.tools_dao.find_connection_by_provider_id(
            provider_connection_id=provider_connection_id,
        )

    async def activate_connection_by_provider_connection_id(
        self,
        *,
        provider_connection_id: str,
    ) -> Optional[ToolConnection]:
        """Mark a connection valid+active after OAuth completes (no project_id needed)."""
        return await self.tools_dao.activate_connection_by_provider_id(
            provider_connection_id=provider_connection_id,
        )

    async def list_connections(
        self,
        *,
        project_id: UUID,
        provider_key: str,
        integration_key: str,
    ) -> List[ToolConnection]:
        """List connections for a specific integration (catalog enrichment)."""
        return await self.tools_dao.query_connections(
            project_id=project_id,
            provider_key=provider_key,
            integration_key=integration_key,
        )

    async def get_connection(
        self,
        *,
        project_id: UUID,
        connection_id: UUID,
    ) -> Optional[ToolConnection]:
        conn = await self.tools_dao.get_connection(
            project_id=project_id,
            connection_id=connection_id,
        )

        if not conn:
            return None

        # If not yet valid, poll the adapter for updated status
        if not conn.is_valid and conn.provider_connection_id:
            adapter = self.adapter_registry.get(conn.provider_key.value)
            status_info = await adapter.get_connection_status(
                provider_connection_id=conn.provider_connection_id,
            )

            if status_info.get("is_valid") and not conn.is_valid:
                conn = await self.tools_dao.update_connection(
                    project_id=project_id,
                    connection_id=connection_id,
                    is_valid=True,
                )

        return conn

    async def create_connection(
        self,
        *,
        project_id: UUID,
        user_id: UUID,
        #
        connection_create: ToolConnectionCreate,
    ) -> ToolConnection:
        provider_key = connection_create.provider_key.value
        integration_key = connection_create.integration_key

        adapter = self.adapter_registry.get(provider_key)

        # Use explicit COMPOSIO_CALLBACK_URL when set (required for external/prod access).
        # Falls back to AGENTA_API_URL for local dev where the proxy handles routing.
        callback_url = env.composio.callback_url or (
            f"{env.agenta.api_url}/preview/tools/connections/callback"
        )

        # Initiate with provider
        provider_result = await adapter.initiate_connection(
            entity_id=str(project_id),
            integration_key=integration_key,
            callback_url=callback_url,
        )

        provider_connection_id = provider_result.get("id")
        auth_config_id = provider_result.get("auth_config_id")
        redirect_url = provider_result.get("redirect_url")

        # Update data with adapter response
        if provider_key == "composio":
            data = connection_create.data or {}
            data["connected_account_id"] = provider_connection_id
            data["auth_config_id"] = auth_config_id
            data["project_id"] = str(project_id)
            if redirect_url:
                data["redirect_url"] = redirect_url
            connection_create.data = data

        # Persist locally
        return await self.tools_dao.create_connection(
            project_id=project_id,
            user_id=user_id,
            #
            connection_create=connection_create,
        )

    async def delete_connection(
        self,
        *,
        project_id: UUID,
        connection_id: UUID,
    ) -> bool:
        # Look up connection
        conn = await self.tools_dao.get_connection(
            project_id=project_id,
            connection_id=connection_id,
        )

        if not conn:
            raise ConnectionNotFoundError(
                connection_id=str(connection_id),
            )

        # Revoke provider-side
        if conn.provider_connection_id:
            adapter = self.adapter_registry.get(conn.provider_key.value)
            try:
                await adapter.revoke_connection(
                    provider_connection_id=conn.provider_connection_id,
                )
            except Exception:
                log.warning(
                    "Failed to revoke provider connection %s, proceeding with local delete",
                    conn.provider_connection_id,
                )

        # Delete locally
        return await self.tools_dao.delete_connection(
            project_id=project_id,
            connection_id=connection_id,
        )

    async def revoke_connection(
        self,
        *,
        project_id: UUID,
        connection_id: UUID,
    ) -> ToolConnection:
        """Mark a connection invalid locally without touching the provider."""
        conn = await self.tools_dao.get_connection(
            project_id=project_id,
            connection_id=connection_id,
        )

        if not conn:
            raise ConnectionNotFoundError(
                connection_id=str(connection_id),
            )

        updated = await self.tools_dao.update_connection(
            project_id=project_id,
            connection_id=connection_id,
            is_valid=False,
        )

        return updated or conn

    async def refresh_connection(
        self,
        *,
        project_id: UUID,
        connection_id: UUID,
        #
        force: bool = False,
    ) -> ToolConnection:
        conn = await self.tools_dao.get_connection(
            project_id=project_id,
            connection_id=connection_id,
        )

        if not conn:
            raise ConnectionNotFoundError(
                connection_id=str(connection_id),
            )

        if not conn.provider_connection_id:
            raise ConnectionNotFoundError(
                connection_id=str(connection_id),
            )

        if not conn.is_active:
            raise ConnectionInactiveError(
                connection_id=str(connection_id),
                detail="Cannot refresh an inactive connection. Create a new connection to re-establish authorization.",
            )

        adapter = self.adapter_registry.get(conn.provider_key.value)
        result = await adapter.refresh_connection(
            provider_connection_id=conn.provider_connection_id,
            force=force,
        )

        redirect_url = result.get("redirect_url")
        data_update = {"redirect_url": redirect_url} if redirect_url else None

        updated = await self.tools_dao.update_connection(
            project_id=project_id,
            connection_id=connection_id,
            is_valid=result.get("is_valid", conn.is_valid),
            data_update=data_update,
        )

        return updated or conn

    # -----------------------------------------------------------------------
    # Tool execution
    # -----------------------------------------------------------------------

    async def execute_tool(
        self,
        *,
        provider_key: str,
        integration_key: str,
        action_key: str,
        provider_connection_id: str,
        entity_id: Optional[str] = None,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a tool action using the provider adapter."""
        adapter = self.adapter_registry.get(provider_key)

        result = await adapter.execute(
            integration_key=integration_key,
            action_key=action_key,
            provider_connection_id=provider_connection_id,
            entity_id=entity_id,
            arguments=arguments,
        )

        # Convert ExecutionResult to dict
        return {
            "data": result.data,
            "error": result.error,
            "successful": result.successful,
        }


