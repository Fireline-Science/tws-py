from abc import ABC, abstractmethod
import re
import time
from typing import Optional, Union, Coroutine, Any


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

    @abstractmethod
    def run_workflow(
        self,
        workflow_definition_id: str,
        workflow_args: dict,
        timeout=600,
        retry_delay=1,
    ) -> Union[dict, Coroutine[Any, Any, dict]]:
        """Execute a workflow and wait for it to complete or fail.

        Args:
            workflow_definition_id: The unique identifier of the workflow definition to execute
            workflow_args: Dictionary of arguments to pass to the workflow
            timeout: Maximum time in seconds to wait for workflow completion (1-3600)
            retry_delay: Time in seconds between status checks (1-60)

        Returns:
            The workflow execution result as a dictionary

        Raises:
            ClientException: If the workflow fails, times out, or if invalid parameters are provided
        """
        pass
