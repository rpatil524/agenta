from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse

from oss.src.utils.exceptions import intercept_exceptions
from oss.src.utils.logging import get_module_logger
from oss.src.utils.caching import get_cache, set_cache
from oss.src.utils.env import is_ee

from oss.src.apis.fastapi.tools.models import (
    ToolToolCatalogActionResponse,
    ToolToolCatalogActionsResponse,
    ToolToolCatalogIntegrationResponse,
    ToolToolCatalogIntegrationsResponse,
    ToolToolCatalogProviderResponse,
    ToolToolCatalogProvidersResponse,
    #
    ToolConnectionCreateRequest,
    ToolConnectionResponse,
    ToolConnectionsResponse,
    #
    ToolQueryRequest,
    ToolResponse,  # noqa: F401
    ToolsResponse,
    #
    ToolCallRequest,  # noqa: F401
    ToolCallResponse,
)
from oss.src.apis.fastapi.tools.utils import (
    merge_tool_query_requests,
    parse_tool_query_request_from_params,
)

from oss.src.core.tools.dtos import (
    ToolCatalogActionDetails,  # noqa: F401
    ToolToolCatalogProviderDetails,  # noqa: F401
    ToolToolCatalogIntegrationDetails,  # noqa: F401
    #
    ToolCall,
    ToolResult,
)
from oss.src.core.tools.service import (
    ToolsService,
)

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
            response_model=ToolToolCatalogProvidersResponse,
            response_model_exclude_none=True,
        )
        self.router.add_api_route(
            "/catalog/providers/{provider_key}",
            self.get_provider,
            methods=["GET"],
            operation_id="get_tool_provider",
            response_model=ToolToolCatalogProviderResponse,
            response_model_exclude_none=True,
        )
        self.router.add_api_route(
            "/catalog/providers/{provider_key}/integrations/",
            self.list_integrations,
            methods=["GET"],
            operation_id="list_tool_integrations",
            response_model=ToolToolCatalogIntegrationsResponse,
            response_model_exclude_none=True,
        )
        self.router.add_api_route(
            "/catalog/providers/{provider_key}/integrations/{integration_key}",
            self.get_integration,
            methods=["GET"],
            operation_id="get_tool_integration",
            response_model=ToolToolCatalogIntegrationResponse,
            response_model_exclude_none=True,
        )
        self.router.add_api_route(
            "/catalog/providers/{provider_key}/integrations/{integration_key}/actions/",
            self.list_actions,
            methods=["GET"],
            operation_id="list_tool_actions",
            response_model=ToolToolCatalogActionsResponse,
            response_model_exclude_none=True,
        )
        self.router.add_api_route(
            "/catalog/providers/{provider_key}/integrations/{integration_key}/actions/{action_key}",
            self.get_action,
            methods=["GET"],
            operation_id="get_tool_action",
            response_model=ToolToolCatalogActionResponse,
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
            "/connections/callback",
            self.callback_connection,
            methods=["GET"],
            operation_id="callback_tool_connection",
            response_model=ToolConnectionResponse,
            response_model_exclude_none=True,
        )

        # --- Tool operations ---
        self.router.add_api_route(
            "/query",
            self.query_tools,
            methods=["POST"],
            operation_id="query_tools",
            response_model=ToolsResponse,
            response_model_exclude_none=True,
        )
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
    ) -> ToolToolCatalogProvidersResponse:
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
            model=ToolToolCatalogProvidersResponse,
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
    ) -> ToolToolCatalogProviderResponse:
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
            model=ToolToolCatalogProviderResponse,
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
        full_details: bool = Query(default=False),
        full_catalog: bool = Query(default=True),
    ) -> ToolToolCatalogIntegrationsResponse:
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
            namespace="tools:catalog:integrations",
            key=cache_key,
            model=ToolToolCatalogIntegrationsResponse,
        )
        if cached:
            return cached

        integrations = await self.tools_service.list_integrations(
            project_id=UUID(request.state.project_id),
            provider_key=provider_key,
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
    ) -> ToolToolCatalogIntegrationResponse:
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
            model=ToolToolCatalogIntegrationResponse,
        )
        if cached:
            return cached

        integration = await self.tools_service.get_integration(
            project_id=UUID(request.state.project_id),
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
        full_details: bool = Query(default=False),
        full_catalog: bool = Query(default=True),
    ) -> ToolToolCatalogActionsResponse:
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
            namespace="tools:catalog:actions",
            key=cache_key,
            model=ToolToolCatalogActionsResponse,
        )
        if cached:
            return cached

        actions = await self.tools_service.list_actions(
            provider_key=provider_key,
            integration_key=integration_key,
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
    ) -> ToolToolCatalogActionResponse:
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
            model=ToolToolCatalogActionResponse,
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
    async def callback_connection(
        self,
        request: Request,
        *,
        state: Optional[str] = Query(default=None),
        code: Optional[str] = Query(default=None),
        error: Optional[str] = Query(default=None),
    ) -> ToolConnectionResponse:
        """Handle OAuth callback and return the updated connection."""
        if error:
            # Parse state to extract connection_id
            # State format from Composio: typically includes connection/account ID
            log.error(f"OAuth callback error: {error}, state: {state}")
            return JSONResponse(
                status_code=400,
                content={"detail": f"OAuth error: {error}"},
            )

        if not state or not code:
            return JSONResponse(
                status_code=400,
                content={"detail": "Missing state or code parameter"},
            )

        # For Composio, the OAuth flow is handled server-side
        # The callback indicates success, but we need to poll the connection status
        # State parameter should contain the connected_account_id

        # Note: In Composio's flow, they handle the OAuth exchange server-side
        # We just need to acknowledge the callback and poll for status updates
        log.info(f"OAuth callback received - state: {state}, code present: {bool(code)}")

        return JSONResponse(
            status_code=200,
            content={
                "message": "OAuth callback received successfully. Poll your connection status to check if it's active.",
                "state": state
            },
        )

    # -----------------------------------------------------------------------
    # Tools
    # -----------------------------------------------------------------------

    @intercept_exceptions()
    async def query_tools(
        self,
        request: Request,
        *,
        query_request_params: Optional[ToolQueryRequest] = Depends(
            parse_tool_query_request_from_params
        ),
    ) -> ToolsResponse:
        if is_ee():
            has_permission = await check_action_access(
                user_uid=request.state.user_id,
                project_id=request.state.project_id,
                permission=Permission.VIEW_TOOLS,
            )
            if not has_permission:
                raise FORBIDDEN_EXCEPTION

        body_json = None
        query_request_body = None

        try:
            body_json = await request.json()
            if body_json:
                query_request_body = ToolQueryRequest(**body_json)
        except Exception:
            pass

        merged = merge_tool_query_requests(
            query_request_params,
            query_request_body,
        )

        tool_query = None
        if merged and merged.tool:
            tool_query = merged.tool

        tools, count = await self.tools_service.query_tools(
            project_id=UUID(request.state.project_id),
            #
            tool_query=tool_query,
            #
            windowing=merged.windowing if merged else None,
        )

        return ToolsResponse(
            count=count,
            tools=tools,
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
                content={"detail": f"Invalid tool slug format: {body.name}. Expected: tools.{{provider}}.{{integration}}.{{action}}[.{{connection}}]"},
            )

        provider_key = slug_parts[1]
        integration_key = slug_parts[2]
        action_key = slug_parts[3]
        connection_slug = slug_parts[4] if len(slug_parts) > 4 else None

        # Look up connection
        if not connection_slug:
            return JSONResponse(
                status_code=400,
                content={"detail": "Connection slug is required for tool execution. Use a tool slug with connection: tools.{provider}.{integration}.{action}.{connection}"},
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
                content={"detail": f"Connection is not valid: {connection_slug}. Please refresh the connection."},
            )

        if not connection.provider_connection_id:
            return JSONResponse(
                status_code=500,
                content={"detail": f"Connection has no provider connection ID: {connection_slug}"},
            )

        # Execute the tool via the adapter
        try:
            execution_result = await self.tools_service.execute_tool(
                provider_key=provider_key,
                integration_key=integration_key,
                action_key=action_key,
                provider_connection_id=connection.provider_connection_id,
                arguments=body.arguments,
            )

            result = ToolResult(
                id=body.id,
                data=execution_result.get("data"),
                status={"message": "success"} if execution_result.get("successful") else {"message": "failed", "error": execution_result.get("error")},
            )

            return ToolCallResponse(result=result)

        except Exception as e:
            log.error(f"Tool execution failed: {e}")
            result = ToolResult(
                id=body.id,
                data=None,
                status={"message": "failed", "error": str(e)},
            )
            return ToolCallResponse(result=result)
