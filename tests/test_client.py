from typing import Any
import pytest
from unittest.mock import patch

from tws import AsyncClient, Client, ClientException, create_client, create_async_client

GOOD_PUBLIC_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoiYW5vbiIsImlhdCI6MTczMzc3MDg4OCwiZXhwIjoyMDQ5MzAzNjg4fQ.geVaN_7Yg1tTj2UjibuSpV1_qTzyEjoBXoVR01X0s_M"
BAD_PUBLIC_KEY = "not-a-valid-jwt"
GOOD_SECRET_KEY = "123e4567-e89b-4d3c-8456-426614174000"
BAD_SECRET_KEY = "not-a-valid-uuid4"
GOOD_URL = "https://fakesupabaseref.supabase.co"
BAD_URL = "not a valid URL"


@pytest.mark.parametrize(
    "public_key,secret_key,api_url,exception_message",
    [
        [None, GOOD_SECRET_KEY, GOOD_URL, "Public key is required"],
        [GOOD_PUBLIC_KEY, None, GOOD_URL, "Secret key is required"],
        [GOOD_PUBLIC_KEY, GOOD_SECRET_KEY, None, "API URL is required"],
        [BAD_PUBLIC_KEY, GOOD_SECRET_KEY, GOOD_URL, "Malformed public key"],
        [GOOD_PUBLIC_KEY, BAD_SECRET_KEY, GOOD_URL, "Malformed secret key"],
        [GOOD_PUBLIC_KEY, GOOD_SECRET_KEY, BAD_URL, "Malformed API URL"],
    ],
)
def test_client_instantiation_exceptions(
    public_key: Any, secret_key: Any, api_url: Any, exception_message: str
) -> None:
    with pytest.raises(ClientException) as exc_info:
        _ = create_client(public_key, secret_key, api_url)
    assert exception_message in str(exc_info.value)


@patch("tws._sync.client.create_supabase_client")
def test_client_unknown_exception(supabase_client):
    supabase_client.side_effect = Exception("Unknown error")
    with pytest.raises(ClientException) as exc_info:
        _ = create_client(GOOD_PUBLIC_KEY, GOOD_SECRET_KEY, GOOD_URL)
    assert "Unable to create API client" in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "public_key,secret_key,api_url,exception_message",
    [
        [None, GOOD_SECRET_KEY, GOOD_URL, "Public key is required"],
        [GOOD_PUBLIC_KEY, None, GOOD_URL, "Secret key is required"],
        [GOOD_PUBLIC_KEY, GOOD_SECRET_KEY, None, "API URL is required"],
        [BAD_PUBLIC_KEY, GOOD_SECRET_KEY, GOOD_URL, "Malformed public key"],
        [
            GOOD_PUBLIC_KEY,
            BAD_SECRET_KEY,
            GOOD_URL,
            "Malformed secret key",
        ],
        [GOOD_PUBLIC_KEY, GOOD_SECRET_KEY, BAD_URL, "Malformed API URL"],
    ],
)
async def test_async_client_instantiation_exceptions(
    public_key: Any, secret_key: Any, api_url: Any, exception_message: str
) -> None:
    with pytest.raises(ClientException) as exc_info:
        _ = await create_async_client(public_key, secret_key, api_url)
    assert exception_message in str(exc_info.value)


@pytest.mark.asyncio
@patch("tws._async.client.create_async_supabase_client")
async def test_async_client_unknown_exception(supabase_client):
    supabase_client.side_effect = Exception("Unknown error")
    with pytest.raises(ClientException) as exc_info:
        _ = await create_async_client(GOOD_PUBLIC_KEY, GOOD_SECRET_KEY, GOOD_URL)
    assert "Unable to create API client" in str(exc_info.value)


def test_client_instantiation():
    client = create_client(GOOD_PUBLIC_KEY, GOOD_SECRET_KEY, GOOD_URL)
    assert isinstance(client, Client)


@pytest.mark.asyncio
async def test_async_client_instantiation():
    client = await create_async_client(GOOD_PUBLIC_KEY, GOOD_SECRET_KEY, GOOD_URL)
    assert isinstance(client, AsyncClient)
