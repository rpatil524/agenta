from typing import List, Optional
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError

from oss.src.utils.logging import get_module_logger
from oss.src.utils.exceptions import suppress_exceptions

from oss.src.core.shared.exceptions import EntityCreationConflict
from oss.src.core.tools.interfaces import ToolsDAOInterface
from oss.src.core.tools.dtos import (
    ToolConnection,
    ToolConnectionCreate,
    ToolConnectionStatus,
)

from oss.src.dbs.postgres.shared.engine import engine
from oss.src.dbs.postgres.tools.dbes import ToolConnectionDBE
from oss.src.dbs.postgres.tools.mappings import (
    map_connection_create_to_dbe,
    map_connection_dbe_to_dto,
)


log = get_module_logger(__name__)


class ToolsDAO(ToolsDAOInterface):
    def __init__(self, *, ToolConnectionDBE: type = ToolConnectionDBE):
        self.ToolConnectionDBE = ToolConnectionDBE

    @suppress_exceptions(exclude=[EntityCreationConflict])
    async def create_connection(
        self,
        *,
        project_id: UUID,
        user_id: UUID,
        #
        connection_create: ToolConnectionCreate,
    ) -> Optional[ToolConnection]:
        dbe = map_connection_create_to_dbe(
            project_id=project_id,
            user_id=user_id,
            #
            dto=connection_create,
        )

        try:
            async with engine.core_session() as session:
                session.add(dbe)
                await session.commit()
                await session.refresh(dbe)

                return map_connection_dbe_to_dto(dbe=dbe)

        except IntegrityError as e:
            error_str = str(e.orig) if e.orig else str(e)
            if "uq_tool_connections_project_provider_integration_slug" in error_str:
                raise EntityCreationConflict(
                    entity="ToolConnection",
                    message="ToolConnection with slug '{{slug}}' already exists for this integration.".replace(
                        "{{slug}}", connection_create.slug
                    ),
                    conflict={
                        "provider_key": connection_create.provider_key,
                        "integration_key": connection_create.integration_key,
                        "slug": connection_create.slug,
                    },
                ) from e
            raise

    @suppress_exceptions(default=None)
    async def get_connection(
        self,
        *,
        project_id: UUID,
        connection_id: UUID,
    ) -> Optional[ToolConnection]:
        async with engine.core_session() as session:
            stmt = (
                select(self.ToolConnectionDBE)
                .filter(self.ToolConnectionDBE.project_id == project_id)
                .filter(self.ToolConnectionDBE.id == connection_id)
                .limit(1)
            )

            result = await session.execute(stmt)
            dbe = result.scalars().first()

            if not dbe:
                return None

            return map_connection_dbe_to_dto(dbe=dbe)

    @suppress_exceptions(default=None)
    async def update_connection(
        self,
        *,
        project_id: UUID,
        connection_id: UUID,
        #
        is_valid: Optional[bool] = None,
        is_active: Optional[bool] = None,
        status: Optional[ToolConnectionStatus] = None,
        provider_connection_id: Optional[str] = None,
    ) -> Optional[ToolConnection]:
        async with engine.core_session() as session:
            stmt = (
                select(self.ToolConnectionDBE)
                .filter(self.ToolConnectionDBE.project_id == project_id)
                .filter(self.ToolConnectionDBE.id == connection_id)
                .limit(1)
            )

            result = await session.execute(stmt)
            dbe = result.scalars().first()

            if not dbe:
                return None

            # Update flags
            if is_valid is not None or is_active is not None:
                flags = dbe.flags or {}
                if is_valid is not None:
                    flags["is_valid"] = is_valid
                if is_active is not None:
                    flags["is_active"] = is_active
                dbe.flags = flags

            # Update provider-specific data
            if provider_connection_id is not None:
                data = dbe.data or {}
                data["connected_account_id"] = provider_connection_id
                dbe.data = data

            if status is not None:
                dbe.status = status.model_dump()

            dbe.updated_at = datetime.now(timezone.utc)

            await session.commit()
            await session.refresh(dbe)

            return map_connection_dbe_to_dto(dbe=dbe)

    @suppress_exceptions(default=False)
    async def delete_connection(
        self,
        *,
        project_id: UUID,
        connection_id: UUID,
    ) -> bool:
        async with engine.core_session() as session:
            stmt = (
                delete(self.ToolConnectionDBE)
                .where(self.ToolConnectionDBE.project_id == project_id)
                .where(self.ToolConnectionDBE.id == connection_id)
            )

            result = await session.execute(stmt)
            await session.commit()

            return result.rowcount > 0

    @suppress_exceptions(default=[])
    async def query_connections(
        self,
        *,
        project_id: UUID,
        #
        provider_key: Optional[str] = None,
        integration_key: Optional[str] = None,
    ) -> List[ToolConnection]:
        async with engine.core_session() as session:
            stmt = select(self.ToolConnectionDBE).filter(
                self.ToolConnectionDBE.project_id == project_id,
            )

            if provider_key:
                stmt = stmt.filter(self.ToolConnectionDBE.provider_key == provider_key)

            if integration_key:
                stmt = stmt.filter(
                    self.ToolConnectionDBE.integration_key == integration_key
                )

            stmt = stmt.order_by(self.ToolConnectionDBE.created_at.desc())

            result = await session.execute(stmt)
            dbes = result.scalars().all()

            return [map_connection_dbe_to_dto(dbe=dbe) for dbe in dbes]
