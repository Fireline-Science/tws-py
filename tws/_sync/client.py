from supabase import create_client as create_supabase_client
from supabase import ClientOptions

from tws.base.client import TWSClient, ClientException


class SyncClient(TWSClient):
    def __init__(
        self,
        public_key: str,
        secret_key: str,
        api_url: str,
    ):
        super().__init__(public_key, secret_key, api_url)
        try:
            self.api_client = create_supabase_client(
                api_url, public_key, self.api_client_options
            )
        except Exception as e:
            if "Invalid API key" in str(e):
                raise ClientException("Malformed public key")
            if "Invalid URL" in str(e):
                raise ClientException("Malformed API URL")


def create_client(public_key: str, secret_key: str, api_url="https://api.tuneni.ai"):
    return SyncClient(public_key, secret_key, api_url)
