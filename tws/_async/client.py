import asyncio
import time
from typing import cast, Dict, Optional

import httpx
from httpx import AsyncClient as AsyncHttpClient

from tws.base.client import TWSClient, ClientException


class AsyncClient(TWSClient):
    """Asynchronous client implementation for TWS API interactions.

    Provides asynchronous methods for interfacing with the TWS API.
    """

    def __init__(self, public_key: str, secret_key: str, api_url: str):
        """Initialize the asynchronous client.

        Args:
            public_key: The TWS public key
            secret_key: The TWS secret key
            api_url: The base URL for your TWS API instance
        """
        super().__init__(public_key, secret_key, api_url)
        self.session = cast(AsyncHttpClient, self.session)

    def create_session(
        self,
        base_url: str,
        headers: Dict[str, str],
    ) -> AsyncHttpClient:
        """Create a new asynchronous HTTP session.

        Args:
            base_url: The base URL for the API
            headers: Dictionary of HTTP headers to include in requests

        Returns:
            A configured asynchronous HTTPX client instance
        """
        return AsyncHttpClient(
            base_url=base_url,
            headers=headers,
            follow_redirects=True,
            http2=True,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        # Close the underlying HTTP session
        await self.session.aclose()

    async def _make_request(
        self,
        method: str,
        uri: str,
        payload: Optional[dict] = None,
        params: Optional[dict] = None,
    ):
        """Make a HTTP request to the TWS API.

        Args:
            method: HTTP method to use (GET, POST, etc)
            uri: API endpoint URI
            payload: Optional request body data
            params: Optional URL query parameters

        Returns:
            Parsed JSON response from the API

        Raises:
            ClientException: If a request error occurs
        """
        try:
            response = await self.session.request(
                method, f"/rest/v1/{uri}", json=payload, params=params
            )
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            raise ClientException(f"Request error occurred: {e}")

    async def _make_rpc_request(
        self, function_name: str, payload: Optional[dict] = None
    ):
        """Make an RPC request to the TWS API.

        Args:
            function_name: Name of the RPC function to call
            payload: Optional request body data

        Returns:
            Parsed JSON response from the API
        """
        return await self._make_request("POST", f"rpc/{function_name}", payload)

    async def run_workflow(
        self,
        workflow_definition_id: str,
        workflow_args: dict,
        timeout=600,
        retry_delay=1,
        tags: Optional[Dict[str, str]] = None,
    ):
        self._validate_workflow_params(timeout, retry_delay)
        self._validate_tags(tags)

        payload = {
            "workflow_definition_id": workflow_definition_id,
            "request_body": workflow_args,
        }
        if tags is not None:
            payload["tags"] = tags

        try:
            result = await self._make_rpc_request("start_workflow", payload)
        except httpx.HTTPStatusError as e:
            if (
                e.response.status_code == 400
                and e.response.json().get("code") == "P0001"
            ):
                raise ClientException("Workflow definition ID not found")
            raise ClientException(f"HTTP error occurred: {e}")

        workflow_instance_id = result["workflow_instance_id"]
        start_time = time.time()

        while True:
            self._check_timeout(start_time, timeout)

            params = {"select": "status,result", "id": f"eq.{workflow_instance_id}"}
            result = await self._make_request(
                "GET", "workflow_instances", params=params
            )

            if not result:
                raise ClientException(
                    f"Workflow instance {workflow_instance_id} not found"
                )

            instance = result[0]
            workflow_result = self._handle_workflow_status(instance)
            if workflow_result is not None:
                return workflow_result

            await asyncio.sleep(retry_delay)
