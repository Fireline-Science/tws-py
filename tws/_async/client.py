import asyncio
import mimetypes
import os
import time
from typing import cast, Dict, Optional

import aiofiles
import httpx
from httpx import AsyncClient as AsyncHttpClient

from tws.base.client import TWS_API_KEY_HEADER, TWSClient, ClientException


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

    async def _lookup_user_id(self) -> str:
        """Look up the user ID associated with the API key.

        Returns:
            The user ID string

        Raises:
            ClientException: If the user ID cannot be found
        """
        if self.user_id is None:
            params = {
                "select": "user_id",
                "api_key": f"eq.{self.session.headers[TWS_API_KEY_HEADER]}",
            }
            try:
                response = await self._make_request(
                    "GET", "users_private", params=params
                )
                if not response or len(response) == 0:
                    raise ClientException("User ID not found, is your API key correct?")
                self.user_id = response[0]["user_id"]
            except Exception as e:
                raise ClientException(f"Failed to look up user ID: {e}")

        return self.user_id

    async def _make_request(
        self,
        method: str,
        uri: str,
        payload: Optional[dict] = None,
        params: Optional[dict] = None,
        files: Optional[dict] = None,
        service: str = "rest",
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
                method, f"/{service}/v1/{uri}", json=payload, params=params, files=files
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

    async def _upload_file(self, file_path: str) -> str:
        """Upload a file to the TWS API asynchronously.

        Args:
            file_path: Path to the file to upload

        Returns:
            File path that can be used in workflow arguments

        Raises:
            ClientException: If the file upload fails
        """
        try:
            if not os.path.exists(file_path):
                raise ClientException(f"File not found: {file_path}")

            filename = os.path.basename(file_path)
            unique_filename = f"{int(time.time())}-{filename}"

            # Detect MIME type based on file extension
            content_type, _ = mimetypes.guess_type(file_path)
            if content_type is None:
                content_type = "application/octet-stream"

            async with aiofiles.open(file_path, "rb") as file_obj:
                file_content = await file_obj.read()
            user_id = await self._lookup_user_id()

            # Since httpx can't handle the aiofiles file object, we have to
            # explicitly construct the tuple so it sends the MIME type
            files = {"upload-file": (filename, file_content, content_type)}

            response = await self._make_request(
                "POST",
                f"object/documents/{user_id}/{unique_filename}",
                files=files,
                service="storage",
            )

            file_url = response["Key"]
            if file_url.startswith("documents/"):
                # Strip the prefix, as the workflow automatically looks in the bucket
                return file_url[len("documents/") :]

            return file_url
        except Exception as e:
            raise ClientException(f"File upload failed: {e}")

    async def run_workflow(
        self,
        workflow_definition_id: str,
        workflow_args: dict,
        timeout=600,
        retry_delay=1,
        tags: Optional[Dict[str, str]] = None,
        files: Optional[Dict[str, str]] = None,
    ):
        self._validate_workflow_params(timeout, retry_delay)
        self._validate_tags(tags)
        self._validate_files(files)

        # Create a copy of workflow_args to avoid modifying the original
        merged_args = workflow_args.copy()

        # Handle file uploads if provided
        if files:
            for arg_name, file_path in files.items():
                # Upload the file and get a file ID
                file_url = await self._upload_file(file_path)
                # Merge the file ID into the workflow arguments
                merged_args[arg_name] = file_url

        payload = {
            "workflow_definition_id": workflow_definition_id,
            "request_body": merged_args,
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
