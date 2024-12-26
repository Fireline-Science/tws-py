from typing import Any
import pytest
from unittest.mock import patch

from postgrest import APIError

from tws import AsyncClient, Client, ClientException, create_client, create_async_client

GOOD_PUBLIC_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoiYW5vbiIsImlhdCI6MTczMzc3MDg4OCwiZXhwIjoyMDQ5MzAzNjg4fQ.geVaN_7Yg1tTj2UjibuSpV1_qTzyEjoBXoVR01X0s_M"
BAD_PUBLIC_KEY = "not-a-valid-jwt"
GOOD_SECRET_KEY = "123e4567-e89b-4d3c-8456-426614174000"
BAD_SECRET_KEY = "not-a-valid-uuid4"
GOOD_URL = "https://fakesupabaseref.supabase.co"
BAD_URL = "not a valid URL"


@pytest.fixture
def good_client():
    return create_client(GOOD_PUBLIC_KEY, GOOD_SECRET_KEY, GOOD_URL)


@pytest.fixture
async def good_async_client():
    return await create_async_client(GOOD_PUBLIC_KEY, GOOD_SECRET_KEY, GOOD_URL)


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


def test_client_instantiation(good_client):
    assert isinstance(good_client, Client)


@pytest.mark.asyncio
async def test_async_client_instantiation(good_async_client):
    assert isinstance(await good_async_client, AsyncClient)


@pytest.mark.parametrize(
    "timeout,retry_delay,exception_message",
    [
        [0, 1, "Timeout must be between 1 and 3600 seconds"],
        [3601, 1, "Timeout must be between 1 and 3600 seconds"],
        [-1, 1, "Timeout must be between 1 and 3600 seconds"],
        ["not a number", 1, "Timeout must be between 1 and 3600 seconds"],
        [600, 0, "Retry delay must be between 1 and 60 seconds"],
        [600, 61, "Retry delay must be between 1 and 60 seconds"],
        [600, -1, "Retry delay must be between 1 and 60 seconds"],
        [600, "not a number", "Retry delay must be between 1 and 60 seconds"],
    ],
)
def test_run_workflow_validation(good_client, timeout, retry_delay, exception_message):
    with pytest.raises(ClientException) as exc_info:
        good_client.run_workflow(
            "workflow-id",
            {"arg": "value"},
            timeout=timeout,
            retry_delay=retry_delay,
        )
    assert exception_message in str(exc_info.value)


@patch("tws._sync.client.SyncSupabaseClient.rpc")
def test_run_workflow_not_found(mock_rpc, good_client):
    mock_rpc.return_value.execute.side_effect = APIError(
        {"message": "Workflow not found", "code": "P0001"}
    )

    with pytest.raises(ClientException) as exc_info:
        good_client.run_workflow("non-existent-workflow", {"arg": "value"})
    assert "Workflow definition ID not found" in str(exc_info.value)


@patch("tws._sync.client.SyncSupabaseClient.rpc")
def test_run_workflow_bad_request(mock_rpc, good_client):
    mock_rpc.return_value.execute.side_effect = APIError(
        {"message": "Bad request", "code": "PXXXX"}
    )

    with pytest.raises(ClientException) as exc_info:
        good_client.run_workflow("workflow-id", {"bad": "args"})
    assert "Bad request" in str(exc_info.value)


@patch("tws._sync.client.SyncSupabaseClient.rpc")
@patch("tws._sync.client.SyncSupabaseClient.table")
def test_run_workflow_success(mock_table, mock_rpc, good_client):
    # Mock successful workflow start
    mock_rpc.return_value.execute.return_value.data = {"workflow_instance_id": "123"}

    # Mock successful completion
    mock_table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"status": "COMPLETED", "result": {"output": "success"}}
    ]

    result = good_client.run_workflow("workflow-id", {"arg": "value"})
    assert result == {"output": "success"}


@patch("tws._sync.client.SyncSupabaseClient.rpc")
@patch("tws._sync.client.SyncSupabaseClient.table")
@patch("time.sleep")
@patch("time.time")
def test_run_workflow_success_after_polling(
    mock_time, mock_sleep, mock_table, mock_rpc, good_client
):
    # Mock successful workflow start
    mock_rpc.return_value.execute.return_value.data = {"workflow_instance_id": "123"}

    # Mock running status first, then completed
    mock_table.return_value.select.return_value.eq.return_value.execute.side_effect = [
        type("obj", (object,), {"data": [{"status": "RUNNING", "result": None}]})(),
        type(
            "obj",
            (object,),
            {
                "data": [
                    {"status": "COMPLETED", "result": {"output": "success after poll"}}
                ]
            },
        )(),
        type(
            "obj",
            (object,),
            {
                "data": [
                    {"status": "COMPLETED", "result": {"output": "success after poll"}}
                ]
            },
        )(),
    ]

    # Mock time to avoid timeout
    mock_time.side_effect = [0, 1, 1]

    result = good_client.run_workflow("workflow-id", {"arg": "value"})

    # Verify sleep was called once with retry_delay
    mock_sleep.assert_called_once_with(1)
    assert result == {"output": "success after poll"}


@patch("tws._sync.client.SyncSupabaseClient.rpc")
@patch("tws._sync.client.SyncSupabaseClient.table")
def test_run_workflow_failure(mock_table, mock_rpc, good_client):
    # Mock successful workflow start
    mock_rpc.return_value.execute.return_value.data = {"workflow_instance_id": "123"}

    # Mock failed execution
    mock_table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"status": "FAILED", "result": {"error": "workflow failed"}}
    ]

    with pytest.raises(ClientException) as exc_info:
        good_client.run_workflow("workflow-id", {"arg": "value"})
    assert "Workflow execution failed" in str(exc_info.value)


@patch("tws._sync.client.SyncSupabaseClient.rpc")
@patch("tws._sync.client.SyncSupabaseClient.table")
def test_run_workflow_instance_not_found(mock_table, mock_rpc, good_client):
    # Mock successful workflow start
    mock_rpc.return_value.execute.return_value.data = {"workflow_instance_id": "123"}

    # Mock instance not found
    mock_table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    with pytest.raises(ClientException) as exc_info:
        good_client.run_workflow("workflow-id", {"arg": "value"})
    assert "Workflow instance 123 not found" in str(exc_info.value)


@patch("tws._sync.client.SyncSupabaseClient.rpc")
@patch("tws._sync.client.SyncSupabaseClient.table")
@patch("time.time")
def test_run_workflow_timeout(mock_time, mock_table, mock_rpc, good_client):
    # Mock successful workflow start
    mock_rpc.return_value.execute.return_value.data = {"workflow_instance_id": "123"}

    # Mock running status
    mock_table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"status": "RUNNING", "result": None}
    ]

    # Mock time to trigger timeout
    mock_time.side_effect = [0, 601]  # Start time and check time

    with pytest.raises(ClientException) as exc_info:
        good_client.run_workflow("workflow-id", {"arg": "value"}, timeout=600)
    assert "Workflow execution timed out after 600 seconds" in str(exc_info.value)
