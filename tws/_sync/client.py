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
        self, workflow_definition_id: str, workflow_args: dict, timeout=600
    ):
        # Invoke the rpc call
        # TODO what exception to raise if this fails?
        result = self.api_client.rpc(
            "start_workflow",
            {
                "workflow_definition_id": workflow_definition_id,
            },
        ).execute()

        # TODO do we assume the response must have a workflow_instance_id?
        workflow_instance_id = result.data["workflow_instance_id"]


def create_client(public_key: str, secret_key: str, api_url: str):
    return SyncClient.create(public_key, secret_key, api_url)
