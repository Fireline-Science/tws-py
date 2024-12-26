from supabase import create_async_client as create_async_supabase_client
from supabase import AsyncClient as SupabaseAsyncClient, AsyncClientOptions

from tws.base.client import TWSClient, ClientException


class AsyncClient(TWSClient):
    api_client_options: AsyncClientOptions
    api_client: SupabaseAsyncClient

    @classmethod
    async def create(cls, public_key: str, secret_key: str, api_url: str):
        self = cls(public_key, secret_key, api_url)
        try:
            self.api_client_options = AsyncClientOptions(
                headers={"Authorization": secret_key}
            )
            self.api_client = await create_async_supabase_client(
                api_url, public_key, self.api_client_options
            )
        except Exception as e:
            if "Invalid API key" in str(e):
                raise ClientException("Malformed public key")
            if "Invalid URL" in str(e):
                raise ClientException("Malformed API URL")
            raise ClientException("Unable to create API client")

        return self

    async def run_workflow(
        self,
        workflow_definition_id: str,
        workflow_args: dict,
        timeout=600,
        retry_delay=1,
    ):
        pass


async def create_client(public_key: str, secret_key: str, api_url: str):
    return await AsyncClient.create(public_key, secret_key, api_url)
