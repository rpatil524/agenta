from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from oss.src.utils.logging import get_module_logger
from oss.src.core.shared.dtos import Windowing

from oss.src.core.tools.dtos import (
    ToolCatalogAction,
    ToolCatalogActionDetails,
    ToolCatalogIntegration,
    ToolCatalogProvider,
    ToolConnection,
    ToolConnectionCreate,
    ToolConnectionStatus,
    Tags,
    ToolQuery,
)
from oss.src.core.tools.interfaces import (
    ToolsDAOInterface,
)
from oss.src.core.tools.adapters.registry import GatewayAdapterRegistry
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
        project_id: UUID,
        provider_key: str,
        #
        search: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[ToolCatalogIntegration]:
        adapter = self.adapter_registry.get(provider_key)
        integrations = await adapter.list_integrations(
            search=search,
            limit=limit,
        )

        # Enrich with local connection counts
        connections = await self.tools_dao.query_connections(
            project_id=project_id,
            provider_key=provider_key,
        )
        counts = _count_by_integration(connections)
        for integration in integrations:
            integration.connections_count = counts.get(integration.key, 0)

        return integrations

    async def get_integration(
        self,
        *,
        project_id: UUID,
        provider_key: str,
        integration_key: str,
    ) -> Optional[ToolCatalogIntegration]:
        adapter = self.adapter_registry.get(provider_key)
        integrations = await adapter.list_integrations()
        target = None
        for i in integrations:
            if i.key == integration_key:
                target = i
                break

        if not target:
            return None

        # Enrich with connection count
        connections = await self.tools_dao.query_connections(
            project_id=project_id,
            provider_key=provider_key,
            integration_key=integration_key,
        )
        target.connections_count = len(connections)

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
    ) -> List[ToolCatalogAction]:
        adapter = self.adapter_registry.get(provider_key)
        return await adapter.list_actions(
            integration_key=integration_key,
            search=search,
            tags=tags,
            important=important,
            limit=limit,
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
    # Tool query (action × connection join)
    # -----------------------------------------------------------------------

    async def query_tools(
        self,
        *,
        project_id: UUID,
        #
        tool_query: Optional[ToolQuery] = None,
        #
        #
        windowing: Optional[Windowing] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Returns (tools, count) where each tool is a dict matching the Tool response model."""
        query = tool_query or ToolQuery()

        # Determine which providers to query
        provider_keys = (
            [query.provider_key] if query.provider_key else self.adapter_registry.keys()
        )

        # 1. Fetch actions from adapters
        all_actions: List[Tuple[str, ToolCatalogAction, ToolCatalogIntegration]] = []
        for pk in provider_keys:
            adapter = self.adapter_registry.get(pk)

            if query.integration_key:
                integration_keys = [query.integration_key]
            else:
                integrations = await adapter.list_integrations()
                integration_keys = [i.key for i in integrations]

            integrations_map: Dict[str, ToolCatalogIntegration] = {}
            for ik in integration_keys:
                integ_list = await adapter.list_integrations()
                for i in integ_list:
                    if i.key == ik:
                        integrations_map[ik] = i
                        break

                actions = await adapter.list_actions(
                    integration_key=ik,
                    search=query.name,
                    tags=query.tags,
                )
                for action in actions:
                    integ = integrations_map.get(ik)
                    if integ:
                        all_actions.append((pk, action, integ))

        # 2. Fetch connections from DAO
        connections = await self.tools_dao.query_connections(
            project_id=project_id,
            provider_key=query.provider_key,
            integration_key=query.integration_key,
        )
        connections_by_key = _group_by_provider_integration(connections)

        # 3. Expand: action × connection → tools
        tools: List[Dict[str, Any]] = []
        for provider_key, action, integ in all_actions:
            conn_key = (provider_key, integ.key)
            conns = connections_by_key.get(conn_key, [])

            if conns:
                for conn in conns:
                    tools.append(
                        _make_tool(
                            provider_key=provider_key,
                            action=action,
                            integration=integ,
                            connection=conn,
                            connection_slug=conn.slug,
                        )
                    )
            else:
                tools.append(
                    _make_tool(
                        provider_key=provider_key,
                        action=action,
                        integration=integ,
                        connection=None,
                        connection_slug=None,
                    )
                )

        # 4. Apply flags filter
        if query.flags and query.flags.is_connected is not None:
            if query.flags.is_connected:
                tools = [t for t in tools if t.get("connection") is not None]
            else:
                tools = [t for t in tools if t.get("connection") is None]

        # 5. Apply windowing
        if windowing and windowing.limit:
            tools = tools[: windowing.limit]

        return tools, len(tools)

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
            adapter = self.adapter_registry.get(conn.provider_key)
            status_info = await adapter.get_connection_status(
                provider_connection_id=conn.provider_connection_id,
            )

            if status_info.get("is_valid") and not conn.is_valid:
                conn = await self.tools_dao.update_connection(
                    project_id=project_id,
                    connection_id=connection_id,
                    is_valid=True,
                    status=status_info.get("status"),
                )

        return conn

    async def create_connection(
        self,
        *,
        project_id: UUID,
        user_id: UUID,
        #
        provider_key: str,
        integration_key: str,
        #
        connection_create: ToolConnectionCreate,
    ) -> ToolConnection:
        adapter = self.adapter_registry.get(provider_key)

        # Extract callback_url from data
        callback_url = None
        if connection_create.data:
            callback_url = connection_create.data.get("callback_url")

        # Initiate with provider
        provider_result = await adapter.initiate_connection(
            entity_id=f"project_{project_id}",
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
            connection_create.data = data

        # Set provider/integration keys in connection_create
        connection_create.provider_key = provider_key
        connection_create.integration_key = integration_key

        # Persist locally
        connection = await self.tools_dao.create_connection(
            project_id=project_id,
            user_id=user_id,
            #
            connection_create=connection_create,
        )

        # Set ephemeral redirect_url in status if present
        if redirect_url and connection:
            connection.status = connection.status or ToolConnectionStatus()
            connection.status.redirect_url = redirect_url

        return connection

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
            adapter = self.adapter_registry.get(conn.provider_key)
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

        adapter = self.adapter_registry.get(conn.provider_key)
        result = await adapter.refresh_connection(
            provider_connection_id=conn.provider_connection_id,
            force=force,
        )

        updated = await self.tools_dao.update_connection(
            project_id=project_id,
            connection_id=connection_id,
            is_valid=result.get("is_valid", conn.is_valid),
            status=result.get("status"),
        )

        connection = updated or conn

        # Set ephemeral redirect_url in status if present
        redirect_url = result.get("redirect_url")
        if redirect_url:
            connection.status = connection.status or ToolConnectionStatus()
            connection.status.redirect_url = redirect_url

        return connection

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
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a tool action using the provider adapter."""
        adapter = self.adapter_registry.get(provider_key)

        result = await adapter.execute(
            integration_key=integration_key,
            action_key=action_key,
            provider_connection_id=provider_connection_id,
            arguments=arguments,
        )

        # Convert ExecutionResult to dict
        return {
            "data": result.data,
            "error": result.error,
            "successful": result.successful,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _count_by_integration(connections: List[ToolConnection]) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for conn in connections:
        counts[conn.integration_key] += 1
    return dict(counts)


def _group_by_provider_integration(
    connections: List[ToolConnection],
) -> Dict[Tuple[str, str], List[ToolConnection]]:
    groups: Dict[Tuple[str, str], List[ToolConnection]] = defaultdict(list)
    for conn in connections:
        groups[(conn.provider_key, conn.integration_key)].append(conn)
    return dict(groups)


def _make_tool(
    *,
    provider_key: str,
    action: ToolCatalogAction,
    integration: ToolCatalogIntegration,
    connection: Optional[ToolConnection],
    connection_slug: Optional[str],
) -> Dict[str, Any]:
    slug_parts = ["tools", provider_key, integration.key, action.key]
    if connection_slug:
        slug_parts.append(connection_slug)

    tool: Dict[str, Any] = {
        "slug": ".".join(slug_parts),
        "action_key": action.key,
        "name": action.name,
        "description": action.description,
        "tags": action.tags,
        "provider_key": provider_key,
        "integration_key": integration.key,
        "integration_name": integration.name,
        "integration_logo": integration.logo,
        "connection": None,
    }

    if connection:
        tool["connection"] = {
            "slug": connection.slug,
            "name": connection.name,
            "is_active": connection.is_active,
            "is_valid": connection.is_valid,
        }

    return tool
