from typing import Any, Dict, List, Optional, Tuple

import httpx

from oss.src.utils.logging import get_module_logger

from agenta.sdk.models.workflows import JsonSchemas

from oss.src.core.tools.dtos import (
    ToolCatalogAction,
    ToolCatalogActionDetails,
    ToolCatalogIntegration,
    ToolCatalogProvider,
    ToolExecutionRequest,
    ToolExecutionResponse,
)
from oss.src.core.tools.interfaces import GatewayAdapterInterface
from oss.src.core.tools.exceptions import AdapterError
from oss.src.core.tools.providers.composio import catalog


log = get_module_logger(__name__)

COMPOSIO_DEFAULT_API_URL = "https://backend.composio.dev/api/v3"


class ComposioAdapter(GatewayAdapterInterface):
    """Composio V3 API adapter — uses httpx directly (no SDK)."""

    def __init__(
        self,
        *,
        api_key: str,
        api_url: str = COMPOSIO_DEFAULT_API_URL,
    ):
        self.api_key = api_key
        self.api_url = api_url.rstrip("/")

    def _headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    async def _get(
        self,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.api_url}{path}",
                headers=self._headers(),
                params=params,
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()

    async def _post(
        self,
        path: str,
        *,
        json: Optional[Dict[str, Any]] = None,
    ) -> Any:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.api_url}{path}",
                headers=self._headers(),
                json=json or {},
                timeout=30.0,
            )
            if not resp.is_success:
                log.error(
                    "Composio POST %s → %s: %s",
                    path,
                    resp.status_code,
                    resp.text,
                )
            resp.raise_for_status()
            return resp.json()

    async def _delete(self, path: str) -> bool:
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{self.api_url}{path}",
                headers=self._headers(),
                timeout=30.0,
            )
            resp.raise_for_status()
            return True

    # -----------------------------------------------------------------------
    # Catalog
    # -----------------------------------------------------------------------

    async def list_providers(self) -> List[ToolCatalogProvider]:
        integrations_count = await catalog.count_integrations(
            api_key=self.api_key,
            api_url=self.api_url,
        )
        return [
            ToolCatalogProvider(
                key="composio",
                name="Composio",
                description="Third-party tool integrations via Composio",
                integrations_count=integrations_count,
            )
        ]

    async def list_integrations(
        self,
        *,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> Tuple[List[ToolCatalogIntegration], Optional[str], int]:
        return await catalog.list_integrations(
            api_key=self.api_key,
            api_url=self.api_url,
            search=search,
            sort_by=sort_by,
            limit=limit,
            cursor=cursor,
        )

    async def list_actions(
        self,
        *,
        integration_key: str,
        query: Optional[str] = None,
        categories: Optional[List[str]] = None,
        important: Optional[bool] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> Tuple[List[ToolCatalogAction], Optional[str], int]:
        return await catalog.list_actions(
            integration_key=integration_key,
            api_key=self.api_key,
            api_url=self.api_url,
            query=query,
            tags=categories,  # Our "categories" maps to Composio's "tags" param
            limit=limit,
            cursor=cursor,
        )

    async def get_action(
        self,
        *,
        integration_key: str,
        action_key: str,
    ) -> Optional[ToolCatalogActionDetails]:
        composio_slug = self._to_composio_slug(
            integration_key=integration_key,
            action_key=action_key,
        )

        try:
            item = await self._get(f"/tools/{composio_slug}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise AdapterError(
                provider_key="composio",
                operation="get_action",
                detail=str(e),
            ) from e
        except httpx.HTTPError as e:
            raise AdapterError(
                provider_key="composio",
                operation="get_action",
                detail=str(e),
            ) from e

        input_params = item.get("input_parameters")
        output_params = item.get("output_parameters")

        return ToolCatalogActionDetails(
            key=action_key,
            name=item.get("name", ""),
            description=item.get("description"),
            schemas=JsonSchemas(
                inputs=input_params,
                outputs=output_params,
            )
            if input_params or output_params
            else None,
            scopes=item.get("scopes") or None,
        )

    # -----------------------------------------------------------------------
    # Connections
    # -----------------------------------------------------------------------

    async def initiate_connection(
        self,
        *,
        user_id: str,
        integration_key: str,
        callback_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        # Step 1: resolve auth config for this integration
        try:
            auth_configs = await self._get(
                "/auth_configs",
                params={"toolkit_slugs": integration_key},
            )
        except httpx.HTTPError as e:
            raise AdapterError(
                provider_key="composio",
                operation="initiate_connection.resolve_auth_config",
                detail=str(e),
            ) from e

        items = (
            auth_configs
            if isinstance(auth_configs, list)
            else auth_configs.get("items", [])
        )
        if not items:
            raise AdapterError(
                provider_key="composio",
                operation="initiate_connection",
                detail=f"No auth config found for integration '{integration_key}'",
            )

        # Prefer the auth_config whose toolkit slug matches the requested integration.
        # The API-side filter (toolkit_slugs param) may not be reliable, so we
        # also filter client-side to avoid picking the wrong integration's config.
        matched = [
            item
            for item in items
            if item.get("toolkit", {}).get("slug") == integration_key
        ]
        target = matched[0] if matched else items[0]
        auth_config_id = target.get("id")

        # Step 2: initiate connected account link
        payload: Dict[str, Any] = {
            "user_id": user_id,
            "auth_config_id": auth_config_id,
        }
        if callback_url:
            payload["callback_url"] = callback_url

        try:
            result = await self._post("/connected_accounts/link", json=payload)
        except httpx.HTTPError as e:
            raise AdapterError(
                provider_key="composio",
                operation="initiate_connection",
                detail=str(e),
            ) from e

        return {
            "id": result.get("connected_account_id"),
            "redirect_url": result.get("redirect_url"),
            "auth_config_id": auth_config_id,
        }

    async def get_connection_status(
        self,
        *,
        provider_connection_id: str,
    ) -> Dict[str, Any]:
        try:
            result = await self._get(f"/connected_accounts/{provider_connection_id}")
        except httpx.HTTPError as e:
            raise AdapterError(
                provider_key="composio",
                operation="get_connection_status",
                detail=str(e),
            ) from e

        return {
            "status": result.get("status"),
            "is_valid": result.get("status") == "ACTIVE",
        }

    async def refresh_connection(
        self,
        *,
        provider_connection_id: str,
        force: bool = False,
        callback_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if callback_url:
            payload["callback_url"] = callback_url

        try:
            result = await self._post(
                f"/connected_accounts/{provider_connection_id}/refresh",
                json=payload,
            )
        except httpx.HTTPError as e:
            raise AdapterError(
                provider_key="composio",
                operation="refresh_connection",
                detail=str(e),
            ) from e

        return {
            "status": result.get("status"),
            "is_valid": result.get("status") == "ACTIVE",
            "redirect_url": result.get("redirect_url"),
        }

    async def revoke_connection(
        self,
        *,
        provider_connection_id: str,
    ) -> bool:
        try:
            return await self._delete(f"/connected_accounts/{provider_connection_id}")
        except httpx.HTTPError as e:
            raise AdapterError(
                provider_key="composio",
                operation="revoke_connection",
                detail=str(e),
            ) from e

    # -----------------------------------------------------------------------
    # Execution
    # -----------------------------------------------------------------------

    async def execute(
        self,
        *,
        request: ToolExecutionRequest,
    ) -> ToolExecutionResponse:
        composio_slug = self._to_composio_slug(
            integration_key=request.integration_key,
            action_key=request.action_key,
        )

        payload: Dict[str, Any] = {
            "arguments": request.arguments,
            "connected_account_id": request.provider_connection_id,
        }
        if request.user_id:
            payload["user_id"] = request.user_id

        try:
            result = await self._post(
                f"/tools/execute/{composio_slug}",
                json=payload,
            )
        except httpx.HTTPStatusError as e:
            body = e.response.text if e.response is not None else ""
            raise AdapterError(
                provider_key="composio",
                operation="execute",
                detail=f"{e} — response: {body}",
            ) from e
        except httpx.HTTPError as e:
            raise AdapterError(
                provider_key="composio",
                operation="execute",
                detail=str(e),
            ) from e

        return ToolExecutionResponse(
            data=result.get("data"),
            error=result.get("error"),
            successful=result.get("successful", False),
        )

    # -----------------------------------------------------------------------
    # Slug mapping helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _to_composio_slug(
        *,
        integration_key: str,
        action_key: str,
    ) -> str:
        """Agenta → Composio: gmail + SEND_EMAIL → GMAIL_SEND_EMAIL"""
        return f"{integration_key.upper()}_{action_key}"

    @staticmethod
    def _extract_action_key(
        *,
        composio_slug: str,
        integration_key: str,
    ) -> str:
        """Composio → Agenta: GMAIL_SEND_EMAIL → SEND_EMAIL"""
        prefix = f"{integration_key.upper()}_"
        if composio_slug.startswith(prefix):
            return composio_slug[len(prefix) :]
        return composio_slug
