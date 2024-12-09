from supabase import create_async_client as create_async_supabase_client

from tws.base.client import TWSClient, ClientException


class AsyncClient(TWSClient):
    @classmethod
    async def create(cls, public_key: str, secret_key: str, api_url: str):
        self = cls(public_key, secret_key, api_url)
        try:
            self.api_client = await create_async_supabase_client(
                api_url, public_key, self.api_client_options
            )
        except Exception as e:
            if "Invalid API key" in str(e):
                raise ClientException("Malformed public key")
            if "Invalid URL" in str(e):
                raise ClientException("Malformed API URL")

        return self


async def create_client(
    public_key: str, secret_key: str, api_url="https://api.tuneni.ai"
):
    return await AsyncClient.create(public_key, secret_key, api_url)
