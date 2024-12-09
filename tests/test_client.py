from typing import Any
import pytest

from tws import ClientException, create_client, create_async_client


GOOD_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoiYW5vbiIsImlhdCI6MTczMzc3MDg4OCwiZXhwIjoyMDQ5MzAzNjg4fQ.geVaN_7Yg1tTj2UjibuSpV1_qTzyEjoBXoVR01X0s_M"
BAD_KEY = "not a valid JWT"
GOOD_URL = "https://fakesupabaseref.supabase.co"
BAD_URL = "not a valid URL"


@pytest.mark.parametrize(
    "public_key,secret_key,api_url,exception_message",
    [
        [None, GOOD_KEY, GOOD_URL, "Public key is required"],
        [GOOD_KEY, None, GOOD_URL, "Secret key is required"],
        [BAD_KEY, GOOD_KEY, GOOD_URL, "Malformed public key"],
        [GOOD_KEY, BAD_KEY, GOOD_URL, "Malformed secret key"],
        [GOOD_KEY, GOOD_KEY, BAD_URL, "Malformed API URL"],
    ],
)
def test_client_instantiation_exceptions(
    public_key: Any, secret_key: Any, api_url: Any, exception_message: str
) -> None:
    with pytest.raises(ClientException) as exc_info:
        _ = create_client(public_key, secret_key, api_url)
    assert exception_message in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "public_key,secret_key,api_url,exception_message",
    [
        [None, GOOD_KEY, GOOD_URL, "Public key is required"],
        [GOOD_KEY, None, GOOD_URL, "Secret key is required"],
        [BAD_KEY, GOOD_KEY, GOOD_URL, "Malformed public key"],
        [GOOD_KEY, BAD_KEY, GOOD_URL, "Malformed secret key"],
        [GOOD_KEY, GOOD_KEY, BAD_URL, "Malformed API URL"],
    ],
)
async def test_async_client_instantiation_exceptions(
    public_key: Any, secret_key: Any, api_url: Any, exception_message: str
) -> None:
    with pytest.raises(ClientException) as exc_info:
        _ = await create_async_client(public_key, secret_key, api_url)
    assert exception_message in str(exc_info.value)
