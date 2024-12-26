import time

from postgrest import APIError
from supabase import create_client as create_supabase_client
from supabase import Client as SyncSupabaseClient, ClientOptions

from tws.base.client import TWSClient, ClientException


class SyncClient(TWSClient):
    api_client_options: ClientOptions
    api_client: SyncSupabaseClient

    @classmethod
    def create(cls, public_key: str, secret_key: str, api_url: str):
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
        if not isinstance(timeout, (int, float)) or timeout < 1 or timeout > 3600:
            raise ClientException("Timeout must be between 1 and 3600 seconds")
        if (
            not isinstance(retry_delay, (int, float))
            or retry_delay < 1
            or retry_delay > 60
        ):
            raise ClientException("Retry delay must be between 1 and 60 seconds")

        # TODO add logging
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

        # Poll the workflow instance until it's status changes to "COMPLETED" or "FAILED"
        start_time = time.time()
        while True:
            if time.time() - start_time > timeout:
                raise ClientException(
                    f"Workflow execution timed out after {timeout} seconds"
                )

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
            status = instance.get("status")

            # TODO also handle CANCELLED state
            if status == "COMPLETED":
                return instance.get("result", {})
            elif status == "FAILED":
                raise ClientException(
                    f"Workflow execution failed: {instance.get('result', {})}"
                )

            time.sleep(retry_delay)  # Wait before next poll


def create_client(public_key: str, secret_key: str, api_url: str):
    return SyncClient.create(public_key, secret_key, api_url)
