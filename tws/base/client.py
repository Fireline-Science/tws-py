from abc import ABC, abstractmethod
import re
import time
from typing import Optional, Union, Coroutine, Any, Dict
from urllib.parse import urlparse

from httpx import Client as SyncClient, AsyncClient

from tws.utils import is_valid_jwt

TWS_API_KEY_HEADER = "X-TWS-API-KEY"


class ClientException(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class TWSClient(ABC):
    def __init__(
        self,
        public_key: str,
        secret_key: str,
        api_url: str,
    ):
        if not public_key:
            raise ClientException("Public key is required")
        if not secret_key:
            raise ClientException("Secret key is required")
        if not api_url:
            raise ClientException("API URL is required")

        # Secret key must be a valid UUID v4
        if not re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
            secret_key,
            re.IGNORECASE,
        ):
            raise ClientException("Malformed secret key")

        # API URL must be a valid URL
        if urlparse(api_url).scheme not in {"https", "http"}:
            raise ClientException("Malformed API URL")

        # Public key should look like a valid JWT
        if not is_valid_jwt(public_key):
            raise ClientException("Malformed public key")

        base_url = api_url.rstrip("/")
        headers = {
            "Authorization": f"Bearer {public_key}",
            "apikey": public_key,
            TWS_API_KEY_HEADER: secret_key,
        }
        self.session = self.create_session(base_url, headers)
        self.user_id = None

    @abstractmethod
    def create_session(
        self,
        base_url: str,
        headers: Dict[str, str],
    ) -> Union[SyncClient, AsyncClient]:
        raise NotImplementedError()

    @staticmethod
    def _validate_workflow_params(
        timeout: Union[int, float],
        retry_delay: Union[int, float],
    ) -> None:
        if not isinstance(timeout, (int, float)) or timeout < 1 or timeout > 3600:
            raise ClientException("Timeout must be between 1 and 3600 seconds")
        if (
            not isinstance(retry_delay, (int, float))
            or retry_delay < 1
            or retry_delay > 60
        ):
            raise ClientException("Retry delay must be between 1 and 60 seconds")

    @staticmethod
    def _handle_workflow_status(instance: dict) -> Optional[dict]:
        status = instance.get("status")

        # TODO also handle CANCELLED state
        if status == "COMPLETED":
            return instance.get("result", {})
        elif status == "FAILED":
            raise ClientException(
                f"Workflow execution failed: {instance.get('result', {})}"
            )
        return None

    @staticmethod
    def _check_timeout(start_time: float, timeout: Union[int, float]) -> None:
        if time.time() - start_time > timeout:
            raise ClientException(
                f"Workflow execution timed out after {timeout} seconds"
            )

    @staticmethod
    def _normalize_workflow_result(instance: dict, workflow_result: dict) -> dict:
        """Normalize workflow instance data into a standard response format.

        Args:
            instance: The workflow instance data from the API
            workflow_result: The processed workflow result

        Returns:
            A normalized dictionary with standard workflow response fields
        """
        return {
            "id": instance.get("id"),
            "workflow_definition_id": instance.get("workflow_definition_id"),
            "created_at": instance.get("created_at"),
            "updated_at": instance.get("updated_at"),
            "result": workflow_result,
            "status": instance.get("status"),
            "instance_num": instance.get("instance_num"),
        }

    @staticmethod
    def _validate_tags(tags: Optional[Dict[str, str]]) -> None:
        if tags is not None:
            if not isinstance(tags, dict):
                raise ClientException("Tags must be a dictionary")
            for key, value in tags.items():
                if not isinstance(key, str) or not isinstance(value, str):
                    raise ClientException("Tag keys and values must be strings")
                if len(key) > 255 or len(value) > 255:
                    raise ClientException(
                        "Tag keys and values must be <= 255 characters"
                    )

    @abstractmethod
    def _lookup_user_id(self) -> Union[str, Coroutine[Any, Any, str]]:
        """Look up the user ID associated with the API key.

        Lazily fetches and caches the user ID if it hasn't been retrieved yet.

        Returns:
            The user ID string

        Raises:
            ClientException: If the user ID cannot be found
        """
        raise NotImplementedError()

    @staticmethod
    def _validate_files(files: Optional[Dict[str, str]]) -> None:
        """Validate file upload parameters.

        Args:
            files: Dictionary mapping argument names to file paths

        Raises:
            ClientException: If files parameter is invalid
        """
        if files is not None:
            if not isinstance(files, dict):
                raise ClientException("Files must be a dictionary")
            for key, value in files.items():
                if not isinstance(key, str):
                    raise ClientException("File keys must be strings")

                # Validate that the value is a string (file path)
                if not isinstance(value, str):
                    raise ClientException("File values must be file paths (strings)")

    @abstractmethod
    def run_workflow(
        self,
        workflow_definition_id: str,
        workflow_args: dict,
        timeout=600,
        retry_delay=1,
        tags: Optional[Dict[str, str]] = None,
        files: Optional[Dict[str, str]] = None,
    ) -> Union[dict, Coroutine[Any, Any, dict]]:
        """Execute a workflow and wait for it to complete or fail.

        Args:
            workflow_definition_id: The unique identifier of the workflow definition to execute
            workflow_args: Dictionary of arguments to pass to the workflow
            timeout: Maximum time in seconds to wait for workflow completion (1-3600)
            retry_delay: Time in seconds between status checks (1-60)
            tags: Optional dictionary of tag key-value pairs to attach to the workflow
            files: Optional dictionary mapping workflow argument names to file paths

        Returns:
            The workflow execution result as a dictionary

        Raises:
            ClientException: If the workflow fails, times out, or if invalid parameters are provided
        """
        pass

    @abstractmethod
    def rerun_workflow_with_step_id(
        self,
        workflow_instance_id: str,
        start_from_workflow_step_id: str,
        step_state_overrides: Optional[Dict[str, dict]] = None,
        timeout=600,
        retry_delay=1,
    ) -> Union[dict, Coroutine[Any, Any, dict]]:
        """Rerun a workflow instance from a specific step by ID.

        Args:
            workflow_instance_id: The unique identifier of the workflow instance to rerun
            start_from_workflow_step_id: The workflow step ID to start from
            step_state_overrides: Optional dictionary mapping step slugs to state overrides
            timeout: Maximum time in seconds to wait for workflow completion (1-3600)
            retry_delay: Time in seconds between status checks (1-60)

        Returns:
            The workflow execution result as a dictionary

        Raises:
            ClientException: If the workflow fails, times out, or if invalid parameters are provided
        """
        pass

    @abstractmethod
    def rerun_workflow_with_step_slug(
        self,
        workflow_instance_id: str,
        start_from_slug_name: str,
        step_state_overrides: Optional[Dict[str, dict]] = None,
        timeout=600,
        retry_delay=1,
    ) -> Union[dict, Coroutine[Any, Any, dict]]:
        """Rerun a workflow instance from a specific step by slug.

        Args:
            workflow_instance_id: The unique identifier of the workflow instance to rerun
            start_from_slug_name: The workflow slug name to start from
            step_state_overrides: Optional dictionary mapping step slugs to state overrides
            timeout: Maximum time in seconds to wait for workflow completion (1-3600)
            retry_delay: Time in seconds between status checks (1-60)

        Returns:
            The workflow execution result as a dictionary

        Raises:
            ClientException: If the workflow fails, times out, or if invalid parameters are provided
        """
        pass
