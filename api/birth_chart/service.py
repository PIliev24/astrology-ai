"""
Birth chart database service.

Provides CRUD operations for birth charts with optimized queries
for list views (excludes large chart_data field).
"""

import logging
from typing import List, Optional, Dict, Any

from core.database.base_service import BaseService
from core.exceptions import ChartNotFoundError
from models.database import UserBirthChart, UserBirthChartCreate, UserBirthChartUpdate

logger = logging.getLogger(__name__)


class BirthChartService(BaseService[UserBirthChart, UserBirthChartCreate, UserBirthChartUpdate]):
    """
    Birth chart database operations.

    Extends BaseService with optimized list query that excludes
    the large chart_data field (SVG) for better performance.
    """

    table_name = "user_birth_charts"
    model_class = UserBirthChart
    not_found_error = ChartNotFoundError

    def get_minimal_list(
        self,
        user_id: str,
        limit: Optional[int] = None,
    ) -> List[UserBirthChart]:
        """
        Get charts for list view without chart_data (SVG).

        Optimized for list views - excludes large chart_data field
        to reduce response size and improve performance.

        Args:
            user_id: User ID
            limit: Optional limit on results

        Returns:
            List of charts with empty chart_data
        """
        try:
            query = (
                self.client.table(self.table_name)
                .select("id,user_id,name,birth_data,created_at,updated_at")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
            )

            if limit:
                query = query.limit(limit)

            response = query.execute()

            # Return charts with empty chart_data
            return [
                UserBirthChart(
                    id=item["id"],
                    user_id=item.get("user_id", user_id),
                    name=item["name"],
                    birth_data=item["birth_data"],
                    chart_data={},  # Empty since we didn't select it
                    created_at=item.get("created_at"),
                    updated_at=item.get("updated_at"),
                )
                for item in response.data
            ]

        except Exception as e:
            logger.error(f"Error fetching birth chart list: {e}")
            raise

    def get_birth_data_by_ids(
        self,
        user_id: str,
        chart_ids: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Get birth_data only for specified charts.

        Optimized for compatibility calculations and AI agent tools.
        Does not fetch chart_data to minimize token usage.

        Args:
            user_id: User ID
            chart_ids: List of chart IDs to fetch

        Returns:
            List of dicts with id, name, and birth_data
        """
        if not chart_ids:
            return []

        try:
            response = (
                self.client.table(self.table_name)
                .select("id,name,birth_data")
                .eq("user_id", user_id)
                .in_("id", chart_ids)
                .execute()
            )

            if not response.data:
                raise self.not_found_error()

            # Ensure nation field exists (map from country if needed)
            result = []
            for item in response.data:
                birth_data = item.get("birth_data", {})
                if "country" in birth_data and "nation" not in birth_data:
                    birth_data["nation"] = birth_data["country"]

                result.append({
                    "id": item["id"],
                    "name": item["name"],
                    "birth_data": birth_data,
                })

            return result

        except self.not_found_error:
            raise
        except Exception as e:
            logger.error(f"Error fetching birth data: {e}")
            raise


# Singleton service instance
birth_chart_service = BirthChartService()
