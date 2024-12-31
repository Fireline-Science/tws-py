import time

from postgrest.exceptions import APIError
from supabase import create_client as create_supabase_client
from supabase import Client as SyncSupabaseClient, ClientOptions

from tws.base.client import TWSClient, ClientException


class SyncClient(TWSClient):
    api_client_options: ClientOptions
    api_client: SyncSupabaseClient

    @classmethod
    def create(cls, public_key: str, secret_key: str, api_url: str):
        """Create a new synchronous TWS client instance.

        Args:
            public_key: The TWS public key
            secret_key: The TWS secret key
            api_url: The TWS API URL

        Returns:
            A configured SyncClient instance

        Raises:
            ClientException: If the credentials are invalid or connection fails
        """
        self = cls(public_key, secret_key, api_url)
        try:
            self.api_client_options = ClientOptions(
                headers={"Authorization": secret_key}
            )
            self.api_client = create_supabase_client(
                api_url, public_key, self.api_client_options
            )
        except Exception as e:
            if "Invalid API key" in str(e):
                raise ClientException("Malformed public key")
            if "Invalid URL" in str(e):
                raise ClientException("Malformed API URL")
            raise ClientException("Unable to create API client")

        return self

    def run_workflow(
        self,
        workflow_definition_id: str,
        workflow_args: dict,
        timeout=600,
        retry_delay=1,
    ):
        self._validate_workflow_params(timeout, retry_delay)

        try:
            # Invoke the rpc call
            result = self.api_client.rpc(
                "start_workflow",
                {
                    "workflow_definition_id": workflow_definition_id,
                    "request_body": workflow_args,
                },
            ).execute()
        except APIError as e:
            if e.code == "P0001":
                raise ClientException("Workflow definition ID not found")
            raise ClientException("Bad request")

        workflow_instance_id = result.data["workflow_instance_id"]
        start_time = time.time()

        while True:
            self._check_timeout(start_time, timeout)

            result = (
                self.api_client.table("workflow_instances")
                .select("status,result")
                .eq("id", workflow_instance_id)
                .execute()
            )

            if not result.data:
                raise ClientException(
                    f"Workflow instance {workflow_instance_id} not found"
                )

            instance = result.data[0]
            workflow_result = self._handle_workflow_status(instance)
            if workflow_result is not None:
                return workflow_result

            time.sleep(retry_delay)


def create_client(public_key: str, secret_key: str, api_url: str):
    """Create a new synchronous TWS client instance.

    This is the recommended way to instantiate a synchronous client.

    Args:
        public_key: The TWS public key
        secret_key: The TWS secret key
        api_url: The TWS API URL

    Returns:
        A configured SyncClient instance

    Raises:
        ClientException: If the credentials are invalid or connection fails
    """
    return SyncClient.create(public_key, secret_key, api_url)
