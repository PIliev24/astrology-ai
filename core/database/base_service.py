"""
Generic CRUD service base class for Supabase tables.

Provides common database operations with user isolation,
error handling, and logging. Subclasses should set table_name,
model_class, and not_found_error to customize behavior.

Usage:
    class BirthChartService(BaseService[UserBirthChart, UserBirthChartCreate, UserBirthChartUpdate]):
        table_name = "user_birth_charts"
        model_class = UserBirthChart
        not_found_error = ChartNotFoundError
"""

import logging
from typing import Generic, TypeVar, Type, Optional, List, Any, Dict

from pydantic import BaseModel
from supabase import Client

from core.clients.supabase import get_supabase_client
from core.exceptions import NotFoundError, AppException

logger = logging.getLogger(__name__)

# Type variables for generic typing
ModelT = TypeVar("ModelT", bound=BaseModel)
CreateT = TypeVar("CreateT", bound=BaseModel)
UpdateT = TypeVar("UpdateT", bound=BaseModel)


class BaseService(Generic[ModelT, CreateT, UpdateT]):
    """
    Generic CRUD service for Supabase tables.

    Provides standard create, read, update, delete operations
    with user isolation (all queries filter by user_id).

    Attributes:
        table_name: Name of the Supabase table
        model_class: Pydantic model class for this entity
        not_found_error: Exception class to raise when entity not found
        id_field: Name of the primary key field (default: "id")
        order_by: Default field to order results by (default: "created_at")
        order_desc: Whether to order descending (default: True)
    """

    table_name: str
    model_class: Type[ModelT]
    not_found_error: Type[NotFoundError] = NotFoundError
    id_field: str = "id"
    order_by: str = "created_at"
    order_desc: bool = True

    def __init__(self, client: Optional[Client] = None):
        """
        Initialize service with optional Supabase client.

        Args:
            client: Supabase client instance. If not provided,
                   uses the global singleton.
        """
        self._client = client

    @property
    def client(self) -> Client:
        """Get Supabase client, using singleton if not injected."""
        if self._client is None:
            return get_supabase_client()
        return self._client

    def _handle_not_found(self, error: Exception, entity_name: str = "Resource") -> None:
        """
        Check if error is a Supabase "no rows" error and raise appropriate exception.

        Args:
            error: The exception to check
            entity_name: Name of the entity for error messages
        """
        error_str = str(error)
        if "PGRST116" in error_str or "Cannot coerce the result to a single JSON object" in error_str:
            raise self.not_found_error()

    def create(self, user_id: str, data: CreateT) -> ModelT:
        """
        Create a new record.

        Args:
            user_id: User ID for ownership
            data: Data to create

        Returns:
            Created record as model instance

        Raises:
            AppException: If creation fails
        """
        try:
            insert_data = {"user_id": user_id, **data.model_dump(exclude_none=True)}
            response = self.client.table(self.table_name).insert(insert_data).execute()

            if not response.data:
                raise AppException(message=f"Failed to create {self.table_name}")

            logger.info(f"Created {self.table_name} for user {user_id}")
            return self.model_class(**response.data[0])

        except AppException:
            raise
        except Exception as e:
            logger.error(f"Error creating {self.table_name}: {e}")
            raise AppException(
                message=f"Failed to create {self.table_name}",
                details=str(e)
            )

    def get_by_id(self, user_id: str, record_id: str) -> ModelT:
        """
        Get a single record by ID with user ownership check.

        Args:
            user_id: User ID for ownership verification
            record_id: Record ID

        Returns:
            Record as model instance

        Raises:
            not_found_error: If record not found or not owned by user
        """
        try:
            response = (
                self.client.table(self.table_name)
                .select("*")
                .eq(self.id_field, record_id)
                .eq("user_id", user_id)
                .single()
                .execute()
            )

            if not response.data:
                raise self.not_found_error()

            return self.model_class(**response.data)

        except (self.not_found_error, NotFoundError):
            raise
        except Exception as e:
            self._handle_not_found(e)
            logger.error(f"Error fetching {self.table_name} {record_id}: {e}")
            raise AppException(
                message=f"Failed to fetch {self.table_name}",
                details=str(e)
            )

    def get_all(
        self,
        user_id: str,
        limit: Optional[int] = None,
        select_columns: Optional[str] = None,
    ) -> List[ModelT]:
        """
        Get all records for a user.

        Args:
            user_id: User ID
            limit: Optional limit on results
            select_columns: Optional comma-separated column names to select

        Returns:
            List of records as model instances
        """
        try:
            columns = select_columns or "*"
            query = (
                self.client.table(self.table_name)
                .select(columns)
                .eq("user_id", user_id)
                .order(self.order_by, desc=self.order_desc)
            )

            if limit:
                query = query.limit(limit)

            response = query.execute()
            return [self.model_class(**item) for item in response.data]

        except Exception as e:
            logger.error(f"Error fetching {self.table_name} list: {e}")
            raise AppException(
                message=f"Failed to fetch {self.table_name} list",
                details=str(e)
            )

    def update(
        self,
        user_id: str,
        record_id: str,
        data: UpdateT,
    ) -> ModelT:
        """
        Update a record.

        Args:
            user_id: User ID for ownership verification
            record_id: Record ID
            data: Update data

        Returns:
            Updated record as model instance

        Raises:
            not_found_error: If record not found or not owned by user
        """
        try:
            # Build update dict from non-None fields
            update_dict = {k: v for k, v in data.model_dump().items() if v is not None}

            if not update_dict:
                return self.get_by_id(user_id, record_id)

            response = (
                self.client.table(self.table_name)
                .update(update_dict)
                .eq(self.id_field, record_id)
                .eq("user_id", user_id)
                .execute()
            )

            if not response.data:
                raise self.not_found_error()

            logger.info(f"Updated {self.table_name} {record_id}")
            return self.model_class(**response.data[0])

        except (self.not_found_error, NotFoundError):
            raise
        except Exception as e:
            self._handle_not_found(e)
            logger.error(f"Error updating {self.table_name} {record_id}: {e}")
            raise AppException(
                message=f"Failed to update {self.table_name}",
                details=str(e)
            )

    def delete(self, user_id: str, record_id: str) -> None:
        """
        Delete a record.

        Args:
            user_id: User ID for ownership verification
            record_id: Record ID
        """
        try:
            self.client.table(self.table_name).delete().eq(
                self.id_field, record_id
            ).eq("user_id", user_id).execute()

            logger.info(f"Deleted {self.table_name} {record_id} for user {user_id}")

        except Exception as e:
            logger.error(f"Error deleting {self.table_name} {record_id}: {e}")
            raise AppException(
                message=f"Failed to delete {self.table_name}",
                details=str(e)
            )

    def exists(self, user_id: str, record_id: str) -> bool:
        """
        Check if a record exists and belongs to user.

        Args:
            user_id: User ID
            record_id: Record ID

        Returns:
            True if record exists and belongs to user
        """
        try:
            response = (
                self.client.table(self.table_name)
                .select(self.id_field)
                .eq(self.id_field, record_id)
                .eq("user_id", user_id)
                .execute()
            )
            return bool(response.data)
        except Exception:
            return False

    def count(self, user_id: str) -> int:
        """
        Count records for a user.

        Args:
            user_id: User ID

        Returns:
            Number of records
        """
        try:
            response = (
                self.client.table(self.table_name)
                .select(self.id_field, count="exact")
                .eq("user_id", user_id)
                .execute()
            )
            return response.count or 0
        except Exception as e:
            logger.error(f"Error counting {self.table_name}: {e}")
            return 0
