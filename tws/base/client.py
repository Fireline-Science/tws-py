from abc import ABC, abstractmethod
import re
import time


# TODO something better than Exception?
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
        timeout: int | float,
        retry_delay: int | float,
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
    def _handle_workflow_status(instance: dict, workflow_instance_id: str) -> dict:
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
    def _check_timeout(start_time: float, timeout: int | float) -> None:
        if time.time() - start_time > timeout:
            raise ClientException(
                f"Workflow execution timed out after {timeout} seconds"
            )

    # TODO add docstrings
    @abstractmethod
    def run_workflow(
        self,
        workflow_definition_id: str,
        workflow_args: dict,
        timeout=600,
        retry_delay=1,
    ):
        pass
