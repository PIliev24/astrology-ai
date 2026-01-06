"""
Base API client for external HTTP services.

Provides a reusable pattern for making HTTP requests with
consistent error handling, timeouts, and logging.
"""

import logging
from abc import ABC
from typing import Any, Dict, Optional

import httpx

from core.exceptions import ExternalServiceError, TimeoutError

logger = logging.getLogger(__name__)


class BaseAPIClient(ABC):
    """
    Abstract base class for external API clients.

    Provides consistent HTTP request handling with error handling,
    timeouts, and logging. Subclasses should implement specific
    API methods using the _request helper.

    Usage:
        class MyAPIClient(BaseAPIClient):
            def __init__(self):
                super().__init__(
                    base_url="https://api.example.com",
                    headers={"Authorization": "Bearer token"}
                )

            async def get_resource(self, id: str) -> dict:
                return await self._request("GET", f"/resources/{id}")
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        headers: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize the API client.

        Args:
            base_url: Base URL for all requests (e.g., "https://api.example.com")
            timeout: Request timeout in seconds (default: 30)
            headers: Default headers to include in all requests
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.default_headers = headers or {}

    async def _request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        expected_status: int = 200,
    ) -> Dict[str, Any]:
        """
        Make an HTTP request with standard error handling.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            endpoint: API endpoint (e.g., "/users/123")
            json: JSON body for POST/PUT requests
            params: Query parameters
            headers: Additional headers (merged with defaults)
            expected_status: Expected successful status code (default: 200)

        Returns:
            Parsed JSON response

        Raises:
            ExternalServiceError: If the API returns an error
            TimeoutError: If the request times out
        """
        url = f"{self.base_url}{endpoint}"
        request_headers = {**self.default_headers, **(headers or {})}

        logger.debug(f"API Request: {method} {url}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    json=json,
                    params=params,
                    headers=request_headers,
                )

                if response.status_code != expected_status:
                    logger.error(
                        f"API error: {method} {url} returned {response.status_code}"
                    )
                    raise ExternalServiceError(
                        message=f"External API returned status {response.status_code}",
                        details={
                            "status_code": response.status_code,
                            "url": url,
                            "method": method,
                        }
                    )

                return response.json()

        except httpx.TimeoutException:
            logger.error(f"API timeout: {method} {url}")
            raise TimeoutError(
                message="External API request timed out",
                details={"url": url, "method": method, "timeout": self.timeout}
            )
        except httpx.RequestError as e:
            logger.error(f"API request failed: {method} {url} - {str(e)}")
            raise ExternalServiceError(
                message=f"API request failed: {str(e)}",
                details={"url": url, "method": method, "error": str(e)}
            )
        except ExternalServiceError:
            raise
        except TimeoutError:
            raise
        except Exception as e:
            logger.error(f"Unexpected API error: {method} {url} - {str(e)}")
            raise ExternalServiceError(
                message="Unexpected error during API request",
                details={"url": url, "method": method, "error": str(e)}
            )

    async def post(
        self,
        endpoint: str,
        json: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make a POST request."""
        return await self._request("POST", endpoint, json=json, headers=headers)

    async def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make a GET request."""
        return await self._request("GET", endpoint, params=params, headers=headers)

    async def put(
        self,
        endpoint: str,
        json: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make a PUT request."""
        return await self._request("PUT", endpoint, json=json, headers=headers)

    async def delete(
        self,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make a DELETE request."""
        return await self._request("DELETE", endpoint, headers=headers)
