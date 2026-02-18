from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse

from oss.src.utils.exceptions import intercept_exceptions
from oss.src.utils.logging import get_module_logger
from oss.src.utils.caching import get_cache, set_cache
from oss.src.utils.common import is_ee

from oss.src.apis.fastapi.tools.models import (
    ToolCatalogActionResponse,
    ToolCatalogActionsResponse,
    ToolCatalogIntegrationResponse,
    ToolCatalogIntegrationsResponse,
    ToolCatalogProviderResponse,
    ToolCatalogProvidersResponse,
    #
    ToolConnectionCreateRequest,
    ToolConnectionResponse,
    ToolConnectionsResponse,
    #
    ToolCallResponse,
)

from oss.src.core.tools.dtos import (
    ToolCatalogActionDetails,  # noqa: F401
    ToolCatalogProviderDetails,  # noqa: F401
    ToolCatalogIntegrationDetails,  # noqa: F401
    #
    ToolCall,
    ToolResult,
)
from oss.src.core.tools.service import (
    ToolsService,
)
from oss.src.utils.env import env

if is_ee():
    from ee.src.models.shared_models import Permission
    from ee.src.utils.permissions import check_action_access, FORBIDDEN_EXCEPTION

log = get_module_logger(__name__)


class ToolsRouter:
    def __init__(
        self,
        *,
        tools_service: ToolsService,
    ):
        self.tools_service = tools_service

        self.router = APIRouter()

        # --- Tool Catalog ---
        self.router.add_api_route(
            "/catalog/providers/",
            self.list_providers,
            methods=["GET"],
            operation_id="list_tool_providers",
            response_model=ToolCatalogProvidersResponse,
            response_model_exclude_none=True,
        )
        self.router.add_api_route(
            "/catalog/providers/{provider_key}",
            self.get_provider,
            methods=["GET"],
            operation_id="get_tool_provider",
            response_model=ToolCatalogProviderResponse,
            response_model_exclude_none=True,
        )
        self.router.add_api_route(
            "/catalog/providers/{provider_key}/integrations/",
            self.list_integrations,
            methods=["GET"],
            operation_id="list_tool_integrations",
            response_model=ToolCatalogIntegrationsResponse,
            response_model_exclude_none=True,
        )
        self.router.add_api_route(
            "/catalog/providers/{provider_key}/integrations/{integration_key}",
            self.get_integration,
            methods=["GET"],
            operation_id="get_tool_integration",
            response_model=ToolCatalogIntegrationResponse,
            response_model_exclude_none=True,
        )
        self.router.add_api_route(
            "/catalog/providers/{provider_key}/integrations/{integration_key}/actions/",
            self.list_actions,
            methods=["GET"],
            operation_id="list_tool_actions",
            response_model=ToolCatalogActionsResponse,
            response_model_exclude_none=True,
        )
        self.router.add_api_route(
            "/catalog/providers/{provider_key}/integrations/{integration_key}/actions/{action_key}",
            self.get_action,
            methods=["GET"],
            operation_id="get_tool_action",
            response_model=ToolCatalogActionResponse,
            response_model_exclude_none=True,
        )

        # --- Tool Connections ---
        self.router.add_api_route(
            "/connections/query",
            self.query_connections,
            methods=["POST"],
            operation_id="query_tool_connections",
            response_model=ToolConnectionsResponse,
            response_model_exclude_none=True,
        )
        self.router.add_api_route(
            "/connections/",
            self.create_connection,
            methods=["POST"],
            operation_id="create_tool_connection",
            response_model=ToolConnectionResponse,
            response_model_exclude_none=True,
        )
        self.router.add_api_route(
            "/connections/callback",
            self.callback_connection,
            methods=["GET"],
            operation_id="callback_tool_connection",
        )
        self.router.add_api_route(
            "/connections/{connection_id}",
            self.get_connection,
            methods=["GET"],
            operation_id="get_tool_connection",
            response_model=ToolConnectionResponse,
            response_model_exclude_none=True,
        )
        self.router.add_api_route(
            "/connections/{connection_id}",
            self.delete_connection,
            methods=["DELETE"],
            operation_id="delete_tool_connection",
            status_code=status.HTTP_204_NO_CONTENT,
        )
        self.router.add_api_route(
            "/connections/{connection_id}/refresh",
            self.refresh_connection,
            methods=["POST"],
            operation_id="refresh_tool_connection",
            response_model=ToolConnectionResponse,
            response_model_exclude_none=True,
        )
        self.router.add_api_route(
            "/connections/{connection_id}/revoke",
            self.revoke_connection,
            methods=["POST"],
            operation_id="revoke_tool_connection",
            response_model=ToolConnectionResponse,
            response_model_exclude_none=True,
        )

        # --- Tool operations ---
        self.router.add_api_route(
            "/call",
            self.call_tool,
            methods=["POST"],
            operation_id="call_tool",
            response_model=ToolCallResponse,
            response_model_exclude_none=True,
        )

    # -----------------------------------------------------------------------
    # Tool Catalog
    # -----------------------------------------------------------------------

    @intercept_exceptions()
    async def list_providers(
        self,
        request: Request,
        *,
        full_details: bool = Query(default=False),
        full_catalog: bool = Query(default=True),
    ) -> ToolCatalogProvidersResponse:
        if is_ee():
            has_permission = await check_action_access(
                project_id=request.state.project_id,
                user_uid=request.state.user_id,
                permission=Permission.VIEW_TOOLS,
            )
            if not has_permission:
                raise FORBIDDEN_EXCEPTION

        cache_key = {
            "full_details": full_details,
            "full_catalog": full_catalog,
        }
        cached = await get_cache(
            project_id=request.state.project_id,
            namespace="tools:catalog:providers",
            key=cache_key,
            model=ToolCatalogProvidersResponse,
        )
        if cached:
            return cached

        providers = await self.tools_service.list_providers()
        items = []

        for provider in providers:
            if full_catalog:
                integrations_response = await self.list_integrations(
                    request=request,
                    provider_key=provider.key,
                    full_details=full_details,
                    full_catalog=full_catalog,
                )
                items.append(
                    ToolCatalogProviderDetails(
                        **provider.model_dump(),
                        integrations=integrations_response.integrations,
                    )
                )
                continue

            items.append(provider)

        response = ToolCatalogProvidersResponse(
            count=len(items),
            providers=items,
        )

        await set_cache(
            project_id=request.state.project_id,
            namespace="tools:catalog:providers",
            key=cache_key,
            value=response,
            ttl=5 * 60,  # 5 minutes
        )

        return response

    @intercept_exceptions()
    async def get_provider(
        self,
        request: Request,
        provider_key: str,
        *,
        full_details: bool = Query(default=True),
        full_catalog: bool = Query(default=False),
    ) -> ToolCatalogProviderResponse:
        if is_ee():
            has_permission = await check_action_access(
                user_uid=request.state.user_id,
                project_id=request.state.project_id,
                permission=Permission.VIEW_TOOLS,
            )
            if not has_permission:
                raise FORBIDDEN_EXCEPTION

        cache_key = {
            "provider_key": provider_key,
            "full_details": full_details,
            "full_catalog": full_catalog,
        }
        cached = await get_cache(
            project_id=request.state.project_id,
            namespace="tools:catalog:provider",
            key=cache_key,
            model=ToolCatalogProviderResponse,
        )
        if cached:
            return cached

        provider = await self.tools_service.get_provider(
            provider_key=provider_key,
        )
        if not provider:
            return JSONResponse(
                status_code=404,
                content={"detail": "Provider not found"},
            )

        if full_catalog:
            integrations_response = await self.list_integrations(
                request=request,
                provider_key=provider.key,
                full_details=full_details,
                full_catalog=full_catalog,
            )
            provider_details = ToolCatalogProviderDetails(
                **provider.model_dump(),
                integrations=integrations_response.integrations,
            )
            response = ToolCatalogProviderResponse(
                count=1,
                provider=provider_details,
            )
        else:
            response = ToolCatalogProviderResponse(
                count=1,
                provider=provider,
            )

        await set_cache(
            project_id=request.state.project_id,
            namespace="tools:catalog:provider",
            key=cache_key,
            value=response,
            ttl=5 * 60,  # 5 minutes
        )

        return response

    @intercept_exceptions()
    async def list_integrations(
        self,
        request: Request,
        provider_key: str,
        *,
        search: Optional[str] = Query(default=None),
        sort_by: Optional[str] = Query(default=None),
        limit: Optional[int] = Query(default=None),
        cursor: Optional[str] = Query(default=None),
        full_details: bool = Query(default=False),
        full_catalog: bool = Query(default=False),
    ) -> ToolCatalogIntegrationsResponse:
        if is_ee():
            has_permission = await check_action_access(
                user_uid=request.state.user_id,
                project_id=request.state.project_id,
                permission=Permission.VIEW_TOOLS,
            )
            if not has_permission:
                raise FORBIDDEN_EXCEPTION

        cache_key = {
            "provider_key": provider_key,
            "search": search,
            "sort_by": sort_by,
            "limit": limit,
            "cursor": cursor,
            "full_details": full_details,
            "full_catalog": full_catalog,
        }
        cached = await get_cache(
            project_id=request.state.project_id,
            namespace="tools:catalog:integrations",
            key=cache_key,
            model=ToolCatalogIntegrationsResponse,
        )
        if cached:
            return cached

        integrations, next_cursor, total = await self.tools_service.list_integrations(
            provider_key=provider_key,
            search=search,
            sort_by=sort_by,
            limit=limit,
            cursor=cursor,
        )
        items = []

        for integration in integrations:
            if full_catalog:
                actions_response = await self.list_actions(
                    request=request,
                    provider_key=provider_key,
                    integration_key=integration.key,
                    full_details=full_details,
                    full_catalog=full_catalog,
                )
                items.append(
                    ToolCatalogIntegrationDetails(
                        **integration.model_dump(),
                        actions=actions_response.actions,
                    )
                )
                continue

            items.append(integration)

        response = ToolCatalogIntegrationsResponse(
            count=len(items),
            total=total,
            cursor=next_cursor,
            integrations=items,
        )

        await set_cache(
            project_id=request.state.project_id,
            namespace="tools:catalog:integrations",
            key=cache_key,
            value=response,
            ttl=5 * 60,  # 5 minutes
        )

        return response

    @intercept_exceptions()
    async def get_integration(
        self,
        request: Request,
        provider_key: str,
        integration_key: str,
        *,
        full_details: bool = Query(default=True),
        full_catalog: bool = Query(default=False),
    ) -> ToolCatalogIntegrationResponse:
        if is_ee():
            has_permission = await check_action_access(
                user_uid=request.state.user_id,
                project_id=request.state.project_id,
                permission=Permission.VIEW_TOOLS,
            )
            if not has_permission:
                raise FORBIDDEN_EXCEPTION

        cache_key = {
            "provider_key": provider_key,
            "integration_key": integration_key,
            "full_details": full_details,
            "full_catalog": full_catalog,
        }
        cached = await get_cache(
            project_id=request.state.project_id,
            namespace="tools:catalog:integration",
            key=cache_key,
            model=ToolCatalogIntegrationResponse,
        )
        if cached:
            return cached

        integration = await self.tools_service.get_integration(
            provider_key=provider_key,
            integration_key=integration_key,
        )
        if not integration:
            return JSONResponse(
                status_code=404,
                content={"detail": "Integration not found"},
            )

        if full_catalog:
            actions_response = await self.list_actions(
                request=request,
                provider_key=provider_key,
                integration_key=integration_key,
                full_details=full_details,
                full_catalog=full_catalog,
            )

            integration_details = ToolCatalogIntegrationDetails(
                **integration.model_dump(),
                actions=actions_response.actions,
            )
            response = ToolCatalogIntegrationResponse(
                count=1,
                integration=integration_details,
            )
        else:
            response = ToolCatalogIntegrationResponse(
                count=1,
                integration=integration,
            )

        await set_cache(
            project_id=request.state.project_id,
            namespace="tools:catalog:integration",
            key=cache_key,
            value=response,
            ttl=5 * 60,  # 5 minutes
        )

        return response

    @intercept_exceptions()
    async def list_actions(
        self,
        request: Request,
        provider_key: str,
        integration_key: str,
        *,
        query: Optional[str] = Query(default=None),
        categories: Optional[List[str]] = Query(default=None),
        limit: Optional[int] = Query(default=None),
        cursor: Optional[str] = Query(default=None),
        full_details: bool = Query(default=False),
        full_catalog: bool = Query(default=False),
    ) -> ToolCatalogActionsResponse:
        if is_ee():
            has_permission = await check_action_access(
                user_uid=request.state.user_id,
                project_id=request.state.project_id,
                permission=Permission.VIEW_TOOLS,
            )
            if not has_permission:
                raise FORBIDDEN_EXCEPTION

        cache_key = {
            "provider_key": provider_key,
            "integration_key": integration_key,
            "query": query,
            "categories": categories,
            "limit": limit,
            "cursor": cursor,
            "full_details": full_details,
            "full_catalog": full_catalog,
        }
        cached = await get_cache(
            project_id=request.state.project_id,
            namespace="tools:catalog:actions",
            key=cache_key,
            model=ToolCatalogActionsResponse,
        )
        if cached:
            return cached

        actions, next_cursor, total = await self.tools_service.list_actions(
            provider_key=provider_key,
            integration_key=integration_key,
            query=query,
            categories=categories,
            limit=limit,
            cursor=cursor,
        )
        items = []

        for action in actions:
            if full_details:
                # Call route handler to benefit from cache reuse
                action_response = await self.get_action(
                    request=request,
                    provider_key=provider_key,
                    integration_key=integration_key,
                    action_key=action.key,
                    full_details=full_details,
                    full_catalog=full_catalog,
                )
                if action_response.action:
                    items.append(action_response.action)
                    continue

            items.append(action)

        response = ToolCatalogActionsResponse(
            count=len(items),
            total=total,
            cursor=next_cursor,
            actions=items,
        )

        await set_cache(
            project_id=request.state.project_id,
            namespace="tools:catalog:actions",
            key=cache_key,
            value=response,
            ttl=5 * 60,  # 5 minutes
        )

        return response

    @intercept_exceptions()
    async def get_action(
        self,
        request: Request,
        provider_key: str,
        integration_key: str,
        action_key: str,
        *,
        full_details: bool = Query(default=True),
        full_catalog: bool = Query(default=False),
    ) -> ToolCatalogActionResponse:
        if is_ee():
            has_permission = await check_action_access(
                user_uid=request.state.user_id,
                project_id=request.state.project_id,
                permission=Permission.VIEW_TOOLS,
            )
            if not has_permission:
                raise FORBIDDEN_EXCEPTION

        cache_key = {
            "provider_key": provider_key,
            "integration_key": integration_key,
            "action_key": action_key,
            "full_details": full_details,
            "full_catalog": full_catalog,
        }
        cached = await get_cache(
            project_id=request.state.project_id,
            namespace="tools:catalog:action",
            key=cache_key,
            model=ToolCatalogActionResponse,
        )
        if cached:
            return cached

        action = await self.tools_service.get_action(
            provider_key=provider_key,
            integration_key=integration_key,
            action_key=action_key,
        )
        if not action:
            return JSONResponse(
                status_code=404,
                content={"detail": "Action not found"},
            )

        response = ToolCatalogActionResponse(
            count=1,
            action=action,
        )

        await set_cache(
            project_id=request.state.project_id,
            namespace="tools:catalog:action",
            key=cache_key,
            value=response,
            ttl=5 * 60,  # 5 minutes
        )

        return response

    # -----------------------------------------------------------------------
    # Tool Connections
    # -----------------------------------------------------------------------

    @intercept_exceptions()
    async def query_connections(
        self,
        request: Request,
        *,
        provider_key: Optional[str] = Query(default=None),
        integration_key: Optional[str] = Query(default=None),
    ) -> ToolConnectionsResponse:
        """Query connections with optional filtering."""
        if is_ee():
            has_permission = await check_action_access(
                user_uid=request.state.user_id,
                project_id=request.state.project_id,
                permission=Permission.VIEW_TOOLS,
            )
            if not has_permission:
                raise FORBIDDEN_EXCEPTION

        connections = await self.tools_service.query_connections(
            project_id=UUID(request.state.project_id),
            provider_key=provider_key,
            integration_key=integration_key,
        )
        return ToolConnectionsResponse(
            count=len(connections),
            connections=connections,
        )

    @intercept_exceptions()
    async def create_connection(
        self,
        request: Request,
        *,
        body: ToolConnectionCreateRequest,
    ) -> ToolConnectionResponse:
        """Create a new tool connection."""
        if is_ee():
            has_permission = await check_action_access(
                user_uid=request.state.user_id,
                project_id=request.state.project_id,
                permission=Permission.EDIT_TOOLS,
            )
            if not has_permission:
                raise FORBIDDEN_EXCEPTION

        if isinstance(body.connection.data, dict):
            body.connection.data = {
                k: v
                for k, v in body.connection.data.items()
                if k not in {"callback_url", "auth_scheme"}
            } or None

        connection = await self.tools_service.create_connection(
            project_id=UUID(request.state.project_id),
            user_id=UUID(request.state.user_id),
            #
            connection_create=body.connection,
        )

        return ToolConnectionResponse(
            count=1,
            connection=connection,
        )

    @intercept_exceptions()
    async def get_connection(
        self,
        request: Request,
        connection_id: UUID,
    ) -> ToolConnectionResponse:
        """Get a connection by ID."""
        if is_ee():
            has_permission = await check_action_access(
                user_uid=request.state.user_id,
                project_id=request.state.project_id,
                permission=Permission.VIEW_TOOLS,
            )
            if not has_permission:
                raise FORBIDDEN_EXCEPTION

        connection = await self.tools_service.get_connection(
            project_id=UUID(request.state.project_id),
            connection_id=connection_id,
        )
        if not connection:
            return JSONResponse(
                status_code=404,
                content={"detail": "Connection not found"},
            )

        return ToolConnectionResponse(
            count=1,
            connection=connection,
        )

    @intercept_exceptions()
    async def delete_connection(
        self,
        request: Request,
        connection_id: UUID,
    ) -> None:
        """Delete a connection by ID."""
        if is_ee():
            has_permission = await check_action_access(
                user_uid=request.state.user_id,
                project_id=request.state.project_id,
                permission=Permission.EDIT_TOOLS,
            )
            if not has_permission:
                raise FORBIDDEN_EXCEPTION

        await self.tools_service.delete_connection(
            project_id=UUID(request.state.project_id),
            connection_id=connection_id,
        )

    @intercept_exceptions()
    async def refresh_connection(
        self,
        request: Request,
        connection_id: UUID,
        *,
        force: bool = Query(default=False),
    ) -> ToolConnectionResponse:
        """Refresh a connection's credentials."""
        if is_ee():
            has_permission = await check_action_access(
                user_uid=request.state.user_id,
                project_id=request.state.project_id,
                permission=Permission.EDIT_TOOLS,
            )
            if not has_permission:
                raise FORBIDDEN_EXCEPTION

        connection = await self.tools_service.refresh_connection(
            project_id=UUID(request.state.project_id),
            connection_id=connection_id,
            force=force,
        )

        return ToolConnectionResponse(
            count=1,
            connection=connection,
        )

    @intercept_exceptions()
    async def revoke_connection(
        self,
        request: Request,
        connection_id: UUID,
    ) -> ToolConnectionResponse:
        """Mark a connection invalid locally (does not revoke at the provider)."""
        if is_ee():
            has_permission = await check_action_access(
                user_uid=request.state.user_id,
                project_id=request.state.project_id,
                permission=Permission.EDIT_TOOLS,
            )
            if not has_permission:
                raise FORBIDDEN_EXCEPTION

        connection = await self.tools_service.revoke_connection(
            project_id=UUID(request.state.project_id),
            connection_id=connection_id,
        )

        return ToolConnectionResponse(
            count=1,
            connection=connection,
        )

    async def callback_connection(
        self,
        request: Request,
        *,
        connected_account_id: Optional[str] = Query(default=None),
        status: Optional[str] = Query(default=None),
        error_message: Optional[str] = Query(default=None),
    ) -> HTMLResponse:
        """Handle OAuth callback from Composio."""
        if error_message or status == "failed":
            log.error("OAuth callback error: %s, status: %s", error_message, status)
            return HTMLResponse(
                status_code=400,
                content=_oauth_card(
                    success=False,
                    error=error_message or "Authorization failed. Please try again.",
                ),
            )

        if not connected_account_id:
            return HTMLResponse(
                status_code=400,
                content=_oauth_card(
                    success=False,
                    error="Missing connection identifier. Please try again.",
                ),
            )

        log.info(
            "OAuth callback received - connected_account_id: %s, status: %s",
            connected_account_id,
            status,
        )

        # Activate the connection and fetch integration details for the card
        integration_label = None
        integration_logo = None
        integration_url = None
        try:
            conn = (
                await self.tools_service.activate_connection_by_provider_connection_id(
                    provider_connection_id=connected_account_id,
                )
            )
            if conn:
                integration_label = conn.integration_key.replace("_", " ").title()
                integration = await self.tools_service.get_integration(
                    provider_key=conn.provider_key.value,
                    integration_key=conn.integration_key,
                )
                if integration:
                    integration_logo = integration.logo
                    integration_url = integration.url
        except Exception:
            pass

        return HTMLResponse(
            status_code=200,
            content=_oauth_card(
                success=True,
                integration_label=integration_label,
                integration_logo=integration_logo,
                integration_url=integration_url,
                agenta_url=env.agenta.web_url,
            ),
        )

    # -----------------------------------------------------------------------
    # Tool Calls
    # -----------------------------------------------------------------------

    @intercept_exceptions()
    async def call_tool(
        self,
        request: Request,
        *,
        body: ToolCall,
    ) -> ToolCallResponse:
        """Call a tool action with a connection."""
        if is_ee():
            has_permission = await check_action_access(
                user_uid=request.state.user_id,
                project_id=request.state.project_id,
                permission=Permission.RUN_TOOLS,
            )
            if not has_permission:
                raise FORBIDDEN_EXCEPTION

        # Parse tool slug: tools.{provider}.{integration}.{action}[.{connection_slug}]
        slug_parts = body.name.split(".")

        if len(slug_parts) < 4 or slug_parts[0] != "tools":
            return JSONResponse(
                status_code=400,
                content={
                    "detail": f"Invalid tool slug format: {body.name}. Expected: tools.{{provider}}.{{integration}}.{{action}}[.{{connection}}]"
                },
            )

        provider_key = slug_parts[1]
        integration_key = slug_parts[2]
        action_key = slug_parts[3]
        connection_slug = slug_parts[4] if len(slug_parts) > 4 else None

        # Look up connection
        if not connection_slug:
            return JSONResponse(
                status_code=400,
                content={
                    "detail": "Connection slug is required for tool execution. Use a tool slug with connection: tools.{provider}.{integration}.{action}.{connection}"
                },
            )

        connections = await self.tools_service.query_connections(
            project_id=UUID(request.state.project_id),
            provider_key=provider_key,
            integration_key=integration_key,
        )

        connection = None
        for conn in connections:
            if conn.slug == connection_slug:
                connection = conn
                break

        if not connection:
            return JSONResponse(
                status_code=404,
                content={"detail": f"Connection not found: {connection_slug}"},
            )

        if not connection.is_active:
            return JSONResponse(
                status_code=400,
                content={"detail": f"Connection is not active: {connection_slug}"},
            )

        if not connection.is_valid:
            return JSONResponse(
                status_code=400,
                content={
                    "detail": f"Connection is not valid: {connection_slug}. Please refresh the connection."
                },
            )

        if not connection.provider_connection_id:
            return JSONResponse(
                status_code=500,
                content={
                    "detail": f"Connection has no provider connection ID: {connection_slug}"
                },
            )

        # Use stored project_id as Composio user_id (matches user_id used during initiation)
        user_id = (
            connection.data.get("project_id")
            if isinstance(connection.data, dict)
            else None
        )

        # Execute the tool via the adapter
        try:
            execution_result = await self.tools_service.execute_tool(
                provider_key=provider_key,
                integration_key=integration_key,
                action_key=action_key,
                provider_connection_id=connection.provider_connection_id,
                user_id=user_id,
                arguments=body.arguments,
            )

            call_id = str(body.id) if body.id else str(uuid4())

            # Pass the full execution envelope (data/error/successful) as
            # result so that schemas.outputs can be applied directly in the FE.
            result = ToolResult(
                id=call_id,
                result=execution_result,
                status={"error": execution_result.get("error")}
                if not execution_result.get("successful")
                else {},
            )

            return ToolCallResponse(call=result)

        except Exception as e:
            log.error(f"Tool execution failed: {e}")
            result = ToolResult(
                id=str(body.id) if body.id else str(uuid4()),
                result=None,
                status={"error": str(e)},
            )
            return ToolCallResponse(call=result)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _oauth_card(
    *,
    success: bool,
    integration_label: Optional[str] = None,
    integration_logo: Optional[str] = None,
    integration_url: Optional[str] = None,
    agenta_url: Optional[str] = None,
    error: Optional[str] = None,
) -> str:
    accent = "#16a34a" if success else "#dc2626"
    agenta_favicon = f"{agenta_url}/assets/favicon.ico" if agenta_url else None

    # Logo row: Agenta <> Integration (or single checkmark/cross on error)
    if success and (agenta_favicon or integration_logo):
        onerror_js = "this.style.display='none'"
        agenta_img = (
            f'<img src="{agenta_favicon}" alt="Agenta" class="logo logo-sm" onerror="{onerror_js}" />'
            if agenta_favicon
            else '<div class="logo-placeholder">A</div>'
        )
        int_alt = integration_label or ""
        int_initial = (integration_label or "?")[0]
        integration_img = (
            f'<img src="{integration_logo}" alt="{int_alt}" class="logo" />'
            if integration_logo
            else f'<div class="logo-placeholder">{int_initial}</div>'
        )
        logos_html = f"""
    <div class="logos">
      {agenta_img}
      <span class="connector">&#8596;</span>
      {integration_img}
    </div>"""
    else:
        icon = "✓" if success else "✕"
        logos_html = f'<div class="status-icon">{icon}</div>'

    # Single-line heading or error message
    if success:
        name = integration_label or "the integration"
        heading_html = f'<p class="h-line"><strong>Agenta</strong> successfully connected to <strong>{name}</strong></p>'
    else:
        heading_html = f'<p class="h-error">{error or "Something went wrong"}</p>'

    agenta_btn = (
        f'<a id="agenta-return-btn" href="{agenta_url}" class="btn btn-primary" onclick="returnToAgenta(event);">Return to Agenta</a>'
        if agenta_url
        else ""
    )
    go_to_label = (
        f"Go to {integration_label}" if integration_label else "Go to Integration"
    )
    integration_btn = (
        f'<a href="{integration_url}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary">{go_to_label}</a>'
        if integration_url
        else ""
    )
    auto_return_html = (
        '<p id="auto-return-text" class="auto-return">This tab will close automatically in 5 seconds...</p>'
        if success and agenta_url
        else ""
    )
    button_html = (
        f'<div class="buttons">{agenta_btn}{integration_btn}</div>{auto_return_html}'
        if agenta_btn or integration_btn
        else auto_return_html
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Agenta ↔ {integration_label or "Integration"}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f4f4f5;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
    }}
    .card {{
      background: #fff;
      border-radius: 16px;
      padding: 48px 40px 40px;
      max-width: 480px;
      width: 90%;
      text-align: center;
      box-shadow: 0 4px 24px rgba(0,0,0,0.08);
    }}
    .logos {{
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 12px;
      margin-bottom: 32px;
    }}
    .logo {{
      width: 48px;
      height: 48px;
      object-fit: contain;
      border-radius: 10px;
    }}
    .logo-sm {{
      width: 32px;
      height: 32px;
      border-radius: 6px;
    }}
    .logo-placeholder {{
      width: 48px;
      height: 48px;
      border-radius: 10px;
      border: 1px solid #e4e4e7;
      background: #f4f4f5;
      color: #71717a;
      font-size: 20px;
      font-weight: 600;
      line-height: 48px;
    }}
    .connector {{
      font-size: 18px;
      color: #a1a1aa;
    }}
    .status-icon {{
      width: 56px;
      height: 56px;
      border-radius: 50%;
      background: {accent}18;
      color: {accent};
      font-size: 26px;
      line-height: 56px;
      margin: 0 auto 32px;
    }}
    .h-line {{
      font-size: 15px;
      font-weight: 400;
      color: #71717a;
      line-height: 1.7;
    }}
    .h-error {{
      font-size: 15px;
      color: {accent};
      line-height: 1.6;
    }}
    .buttons {{
      display: flex;
      flex-direction: column;
      gap: 10px;
      margin-top: 28px;
    }}
    .btn {{
      display: block;
      padding: 10px 24px;
      font-size: 14px;
      font-weight: 500;
      border-radius: 8px;
      text-decoration: none;
      text-align: center;
    }}
    .btn-primary {{
      background: #18181b;
      color: #fff;
    }}
    .btn-primary:hover {{ background: #3f3f46; }}
    .btn-secondary {{
      background: #f4f4f5;
      color: #3f3f46;
    }}
    .btn-secondary:hover {{ background: #e4e4e7; }}
    .auto-return {{
      margin-top: 10px;
      font-size: 12px;
      color: #a1a1aa;
    }}
  </style>
</head>
<body>
  <div class="card">
    {logos_html}
    {heading_html}
    {button_html}
  </div>
  <script>
    function returnToAgenta(event) {{
      if (event) {{
        event.preventDefault();
      }}

      const btn = document.getElementById("agenta-return-btn");
      const target = btn ? btn.getAttribute("href") : null;
      if (!target) {{
        return false;
      }}

      try {{
        if (window.opener && !window.opener.closed) {{
          window.opener.location.href = target;
          window.opener.focus();
          window.close();
          return false;
        }}
      }} catch (_e) {{
        // Fallback to same-tab redirect below.
      }}

      window.location.href = target;
      return false;
    }}

    if (window.opener) {{
      window.opener.postMessage({{type: "tools:oauth:complete"}}, "*");
    }}

    const countdownEl = document.getElementById("auto-return-text");
    if (countdownEl) {{
      let remaining = 5;

      const render = () => {{
        const suffix = remaining === 1 ? "" : "s";
        countdownEl.textContent =
          "This tab will close automatically in " +
          remaining +
          " second" +
          suffix +
          "...";
      }};

      render();
      const intervalId = setInterval(() => {{
        remaining -= 1;
        if (remaining <= 0) {{
          clearInterval(intervalId);
          returnToAgenta();
          return;
        }}
        render();
      }}, 1000);
    }}
  </script>
</body>
</html>"""
