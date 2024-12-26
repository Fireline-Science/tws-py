from abc import ABC, abstractmethod

import re


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

    @abstractmethod
    def run_workflow(
        self,
        workflow_definition_id: str,
        workflow_args: dict,
        timeout=600,
        retry_delay=1,
    ):
        pass
