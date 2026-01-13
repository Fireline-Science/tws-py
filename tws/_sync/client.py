import os
import time
from typing import Any, Dict, cast, Optional

import httpx
from httpx import Client as SyncHttpClient

from tws.base.client import TWS_API_KEY_HEADER, TWSClient, ClientException


class SyncClient(TWSClient):
    """Synchronous client implementation for TWS API interactions.

    Provides synchronous methods for interfacing with the TWS API.
    """

    def __init__(self, public_key: str, secret_key: str, api_url: str):
        """Initialize the synchronous client.

        Args:
            public_key: The TWS public key
            secret_key: The TWS secret key
            api_url: The base URL for your TWS API instance
        """
        super().__init__(public_key, secret_key, api_url)
        self.session = cast(SyncHttpClient, self.session)

    def create_session(
        self,
        base_url: str,
        headers: Dict[str, str],
    ) -> SyncHttpClient:
        """Create a new synchronous HTTP session.

        Args:
            base_url: The base URL for the API
            headers: Dictionary of HTTP headers to include in requests

        Returns:
            A configured synchronous HTTPX client instance
        """
        return SyncHttpClient(
            base_url=base_url,
            headers=headers,
            follow_redirects=True,
            http2=True,
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        # Close the underlying HTTP session
        self.session.close()

    def _lookup_user_id(self) -> str:
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
                response = self._make_request("GET", "users_private", params=params)
                if not response or len(response) == 0:
                    raise ClientException("User ID not found, is your API key correct?")
                self.user_id = response[0]["user_id"]
            except Exception as e:
                raise ClientException(f"Failed to look up user ID: {e}")

        return self.user_id

    def _make_request(
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
            response = self.session.request(
                method, f"/{service}/v1/{uri}", json=payload, params=params, files=files
            )
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            raise ClientException(f"Request error occurred: {e}")

    def _make_rpc_request(self, function_name: str, payload: Optional[dict] = None):
        """Make an RPC request to the TWS API.

        Args:
            function_name: Name of the RPC function to call
            payload: Optional request body data

        Returns:
            Parsed JSON response from the API
        """
        return self._make_request("POST", f"rpc/{function_name}", payload)

    def _upload_file(self, file_path: str) -> str:
        """Upload a file to the TWS API.

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

            with open(file_path, "rb") as file_obj:
                # Upload the file to get a file URL
                unique_filename = f"{int(time.time())}-{filename}"
                user_id = self._lookup_user_id()
                response = self._make_request(
                    "POST",
                    f"object/documents/{user_id}/{unique_filename}",
                    files={"upload-file": file_obj},
                    service="storage",
                )

            file_url = response["Key"]
            # Strip the prefix, as the workflow automatically looks in the bucket
            return file_url[len("documents/") :]
        except Exception as e:
            raise ClientException(f"File upload failed: {e}")

    def run_workflow(
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
                file_url = self._upload_file(file_path)
                # Merge the file ID into the workflow arguments
                merged_args[arg_name] = file_url

        payload = {
            "workflow_definition_id": workflow_definition_id,
            "request_body": merged_args,
        }
        if tags is not None:
            payload["tags"] = tags

        try:
            result = self._make_rpc_request("start_workflow", payload)
        except httpx.HTTPStatusError as e:
            if (
                e.response.status_code == 400
                and e.response.json().get("code") == "P0001"
            ):
                raise ClientException("Workflow definition ID not found")
            raise ClientException(f"HTTP error occurred: {e}")

        # TODO typing on the responses -- codegen?
        workflow_instance_id = result["workflow_instance_id"]
        start_time = time.time()

        while True:
            self._check_timeout(start_time, timeout)

            params = {
                "select": "id,workflow_definition_id,created_at,updated_at,status,result,instance_num",
                "id": f"eq.{workflow_instance_id}",
            }
            result = self._make_request("GET", "workflow_instances", params=params)

            if not result:
                raise ClientException(
                    f"Workflow instance {workflow_instance_id} not found"
                )

            instance = result[0]
            workflow_result = self._handle_workflow_status(instance)
            if workflow_result is not None:
                return self._normalize_workflow_result(instance, workflow_result)

            time.sleep(retry_delay)

    def _rerun_workflow(
        self,
        workflow_instance_id: str,
        start_from_workflow_key: str,
        start_from_workflow_step_value: str,
        timeout: int,
        retry_delay: int,
        step_state_overrides: Optional[Dict[str, dict]] = None,
    ):
        """Rerun a workflow instance from a specific step.

        Args:
            workflow_instance_id: The unique identifier of the workflow instance to rerun
            start_from_workflow_key: The workflow step key to start from ("start_from_slug_name" or "start_from_workflow_step_id")
            start_from_workflow_step_value: The workflow step ID or slug name to start from
            step_state_overrides: Optional dictionary mapping step slugs to state overrides
            timeout: Maximum time in seconds to wait for workflow completion (1-3600)
            retry_delay: Time in seconds between status checks (1-60)

        Returns:
            The workflow execution result as a dictionary

        Raises:
            ClientException: If the workflow fails, times out, or if invalid parameters are provided
        """
        self._validate_workflow_params(timeout, retry_delay)

        payload: dict[str, Any] = {
            "workflow_instance_id": workflow_instance_id,
            start_from_workflow_key: start_from_workflow_step_value,
        }
        if step_state_overrides is not None:
            payload["step_state_overrides"] = step_state_overrides

        try:
            result = self._make_rpc_request("rerun_workflow_instance", payload)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                error_code = e.response.json().get("code")
                error_message = e.response.json().get("message", "")
                if error_code == "DNIED":
                    raise ClientException(
                        "Permission denied to rerun this workflow instance"
                    )
                elif "not found" in error_message.lower():
                    raise ClientException("Workflow instance or step not found")
                elif (
                    "running" in error_message.lower()
                    or "pending" in error_message.lower()
                ):
                    raise ClientException(
                        "Cannot rerun a workflow that is currently running or pending"
                    )
            raise ClientException(f"HTTP error occurred: {e}")

        new_workflow_instance_id = result["new_workflow_instance_id"]
        start_time = time.time()

        while True:
            self._check_timeout(start_time, timeout)

            params = {
                "select": "id,workflow_definition_id,created_at,updated_at,status,result,instance_num",
                "id": f"eq.{new_workflow_instance_id}",
            }
            result = self._make_request("GET", "workflow_instances", params=params)

            if not result:
                raise ClientException(
                    f"Workflow instance {new_workflow_instance_id} not found"
                )

            instance = result[0]
            workflow_result = self._handle_workflow_status(instance)
            if workflow_result is not None:
                return self._normalize_workflow_result(instance, workflow_result)

            time.sleep(retry_delay)

    def rerun_workflow_with_step_slug(
        self,
        workflow_instance_id: str,
        start_from_slug_name: str,
        step_state_overrides: Optional[Dict[str, dict]] = None,
        timeout=600,
        retry_delay=1,
    ):
        """Rerun a workflow instance from a specific step by slug."""
        return self._rerun_workflow(
            workflow_instance_id,
            "start_from_slug_name",
            start_from_slug_name,
            timeout,
            retry_delay,
            step_state_overrides,
        )

    def rerun_workflow_with_step_id(
        self,
        workflow_instance_id: str,
        start_from_workflow_step_id: str,
        step_state_overrides: Optional[Dict[str, dict]] = None,
        timeout=600,
        retry_delay=1,
    ):
        """Rerun a workflow instance from a specific step by ID."""
        return self._rerun_workflow(
            workflow_instance_id,
            "start_from_workflow_step_id",
            start_from_workflow_step_id,
            timeout,
            retry_delay,
            step_state_overrides,
        )
