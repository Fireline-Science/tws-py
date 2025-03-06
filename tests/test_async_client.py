from typing import Any

import httpx
import pytest
from unittest.mock import patch
from httpx import HTTPStatusError, Request, Response

from tests.constants import (
    GOOD_PUBLIC_KEY,
    BAD_PUBLIC_KEY,
    GOOD_SECRET_KEY,
    BAD_SECRET_KEY,
    GOOD_URL,
    BAD_URL,
)
from tws import AsyncClient, ClientException


@pytest.fixture
def good_async_client():
    return AsyncClient(GOOD_PUBLIC_KEY, GOOD_SECRET_KEY, GOOD_URL)


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
async def test_async_client_instantiation_exceptions(
    public_key: Any, secret_key: Any, api_url: Any, exception_message: str
) -> None:
    with pytest.raises(ClientException) as exc_info:
        async with AsyncClient(public_key, secret_key, api_url):
            pass
    assert exception_message in str(exc_info.value)


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
async def test_run_workflow_timing_validation(
    good_async_client, timeout, retry_delay, exception_message
):
    with pytest.raises(ClientException) as exc_info:
        async with good_async_client:
            await good_async_client.run_workflow(
                "workflow-id",
                {"arg": "value"},
                timeout=timeout,
                retry_delay=retry_delay,
            )
    assert exception_message in str(exc_info.value)


@pytest.mark.parametrize(
    "tags,exception_message",
    [
        [{"key": 123}, "Tag keys and values must be strings"],
        [{"key": "value", "bad_key": 123}, "Tag keys and values must be strings"],
        [{123: "value"}, "Tag keys and values must be strings"],
        ["not_a_dict", "Tags must be a dictionary"],
        [{"x" * 256: "value"}, "Tag keys and values must be <= 255 characters"],
        [{"key": "x" * 256}, "Tag keys and values must be <= 255 characters"],
    ],
)
async def test_run_workflow_tag_validation(good_async_client, tags, exception_message):
    with pytest.raises(ClientException) as exc_info:
        async with good_async_client:
            await good_async_client.run_workflow(
                "workflow-id", {"arg": "value"}, tags=tags
            )
    assert exception_message in str(exc_info.value)


@pytest.mark.parametrize(
    "files,exception_message",
    [
        [{"key": 123}, "File values must be file paths (strings)"],
        [{"key": "value", "bad_key": 123}, "File values must be file paths (strings)"],
        [{123: "value"}, "File keys must be strings"],
        ["not_a_dict", "Files must be a dictionary"],
        [{}, None],  # Empty dict is valid
    ],
)
async def test_run_workflow_files_validation(
    good_async_client, files, exception_message
):
    if exception_message:
        with pytest.raises(ClientException) as exc_info:
            async with good_async_client:
                await good_async_client.run_workflow(
                    "workflow-id", {"arg": "value"}, files=files
                )
        assert exception_message in str(exc_info.value)
    else:
        # This should not raise an exception
        async with good_async_client:
            with patch("tws._async.client.AsyncClient._make_rpc_request") as mock_rpc:
                with patch(
                    "tws._async.client.AsyncClient._make_request"
                ) as mock_request:
                    mock_rpc.return_value = {"workflow_instance_id": "123"}
                    mock_request.return_value = [
                        {"status": "COMPLETED", "result": {"output": "success"}}
                    ]
                    await good_async_client.run_workflow(
                        "workflow-id", {"arg": "value"}, files=files
                    )


@patch("tws._async.client.AsyncClient._make_rpc_request")
@patch("tws._async.client.AsyncClient._make_request")
async def test_run_workflow_with_valid_tags(mock_request, mock_rpc, good_async_client):
    # Mock successful workflow start
    mock_rpc.return_value = {"workflow_instance_id": "123"}

    # Mock successful completion
    mock_request.return_value = [
        {"status": "COMPLETED", "result": {"output": "success"}}
    ]

    valid_tags = {"userId": "someUserId", "lessonId": "someLessonId"}

    async with good_async_client:
        result = await good_async_client.run_workflow(
            "workflow-id", {"arg": "value"}, tags=valid_tags
        )

    # Verify tags were included in the RPC payload
    mock_rpc.assert_called_once_with(
        "start_workflow",
        {
            "workflow_definition_id": "workflow-id",
            "request_body": {"arg": "value"},
            "tags": valid_tags,
        },
    )
    assert result == {"output": "success"}


@patch("tws._async.client.AsyncClient._upload_file")
@patch("tws._async.client.AsyncClient._make_rpc_request")
@patch("tws._async.client.AsyncClient._make_request")
async def test_run_workflow_with_files(
    mock_request, mock_rpc, mock_upload, good_async_client, tmp_path
):
    # Create a temporary test file
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("test content")

    # Mock file upload
    mock_upload.return_value = "user-123/timestamp-test_file.txt"

    # Mock successful workflow start
    mock_rpc.return_value = {"workflow_instance_id": "123"}

    # Mock successful completion
    mock_request.return_value = [
        {"status": "COMPLETED", "result": {"output": "success with file"}}
    ]

    files = {"input_file": str(test_file)}

    async with good_async_client:
        result = await good_async_client.run_workflow(
            "workflow-id", {"arg": "value"}, files=files
        )

    # Verify file was uploaded
    mock_upload.assert_called_once_with(str(test_file))

    # Verify the file path was merged into workflow args
    mock_rpc.assert_called_once_with(
        "start_workflow",
        {
            "workflow_definition_id": "workflow-id",
            "request_body": {
                "arg": "value",
                "input_file": "user-123/timestamp-test_file.txt",
            },
        },
    )
    assert result == {"output": "success with file"}


@patch("tws._async.client.AsyncClient._make_rpc_request")
async def test_run_workflow_not_found(mock_rpc, good_async_client):
    mock_request = Request("POST", "http://example.com")
    mock_response = Response(400, request=mock_request)
    mock_response._content = b'{"code": "P0001"}'  # type: ignore

    mock_rpc.side_effect = HTTPStatusError(
        "400 Bad Request", request=mock_request, response=mock_response
    )

    with pytest.raises(ClientException) as exc_info:
        async with good_async_client:
            await good_async_client.run_workflow(
                "non-existent-workflow", {"arg": "value"}
            )
    assert "Workflow definition ID not found" in str(exc_info.value)


@patch("tws._async.client.AsyncClient._make_rpc_request")
async def test_run_workflow_bad_request(mock_rpc, good_async_client):
    mock_request = Request("POST", "http://example.com")
    mock_response = Response(400, request=mock_request)
    mock_response._content = b'{"message": "Bad request", "code": "PXXXX"}'  # type: ignore

    mock_rpc.side_effect = HTTPStatusError(
        "Bad request", request=mock_request, response=mock_response
    )

    with pytest.raises(ClientException) as exc_info:
        async with good_async_client:
            await good_async_client.run_workflow("workflow-id", {"bad": "args"})
    assert "Bad request" in str(exc_info.value)


@patch("tws._async.client.AsyncClient._make_rpc_request")
@patch("tws._async.client.AsyncClient._make_request")
async def test_run_workflow_success(mock_request, mock_rpc, good_async_client):
    # Mock successful workflow start
    mock_rpc.return_value = {"workflow_instance_id": "123"}

    # Mock successful completion
    mock_request.return_value = [
        {"status": "COMPLETED", "result": {"output": "success"}}
    ]

    async with good_async_client:
        result = await good_async_client.run_workflow("workflow-id", {"arg": "value"})
    assert result == {"output": "success"}


@patch("tws._async.client.AsyncClient._make_rpc_request")
@patch("tws._async.client.AsyncClient._make_request")
@patch("asyncio.sleep")
@patch("time.time")
async def test_run_workflow_success_after_polling(
    mock_time, mock_sleep, mock_request, mock_rpc, good_async_client
):
    # Mock successful workflow start
    mock_rpc.return_value = {"workflow_instance_id": "123"}

    # Mock running status first, then completed
    mock_request.side_effect = [
        [{"status": "RUNNING", "result": None}],
        [{"status": "COMPLETED", "result": {"output": "success after poll"}}],
    ]

    # Mock time to avoid timeout
    mock_time.side_effect = [0, 1, 1]

    async with good_async_client:
        result = await good_async_client.run_workflow("workflow-id", {"arg": "value"})

    # Verify sleep was called once with retry_delay
    mock_sleep.assert_called_once_with(1)
    assert result == {"output": "success after poll"}


@patch("tws._async.client.AsyncClient._make_rpc_request")
@patch("tws._async.client.AsyncClient._make_request")
async def test_run_workflow_failure(mock_request, mock_rpc, good_async_client):
    # Mock successful workflow start
    mock_rpc.return_value = {"workflow_instance_id": "123"}

    # Mock failed execution
    mock_request.return_value = [
        {"status": "FAILED", "result": {"error": "workflow failed"}}
    ]

    with pytest.raises(ClientException) as exc_info:
        async with good_async_client:
            await good_async_client.run_workflow("workflow-id", {"arg": "value"})
    assert "Workflow execution failed" in str(exc_info.value)


@patch("tws._async.client.AsyncClient._make_rpc_request")
@patch("tws._async.client.AsyncClient._make_request")
async def test_run_workflow_instance_not_found(
    mock_request, mock_rpc, good_async_client
):
    # Mock successful workflow start
    mock_rpc.return_value = {"workflow_instance_id": "123"}

    # Mock instance not found
    mock_request.return_value = []

    with pytest.raises(ClientException) as exc_info:
        async with good_async_client:
            await good_async_client.run_workflow("workflow-id", {"arg": "value"})
    assert "Workflow instance 123 not found" in str(exc_info.value)


@patch("httpx.AsyncClient.request")
async def test_make_request_success(mock_request, good_async_client):
    mock_response = mock_request.return_value
    mock_response.raise_for_status = lambda: None

    def mock_json():
        return {"data": "test"}

    mock_response.json = mock_json

    async with good_async_client:
        result = await good_async_client._make_request(
            "GET", "test/endpoint", {"param": "value"}, {"query": "param"}
        )

    mock_request.assert_called_once_with(
        "GET",
        "/rest/v1/test/endpoint",
        json={"param": "value"},
        params={"query": "param"},
        files=None,
    )
    assert result == {"data": "test"}


@patch("httpx.AsyncClient.request")
async def test_make_request_error(mock_request, good_async_client):
    mock_request.side_effect = httpx.RequestError("Network error")

    with pytest.raises(ClientException) as exc_info:
        async with good_async_client:
            await good_async_client._make_request("GET", "test/endpoint")

    assert "Request error occurred: Network error" in str(exc_info.value)


@patch("tws._async.client.AsyncClient._make_request")
async def test_lookup_user_id_success(mock_request, good_async_client):
    # Mock successful user ID lookup
    mock_request.return_value = [{"user_id": "test-user-123"}]

    async with good_async_client:
        user_id = await good_async_client._lookup_user_id()

    # Verify the request was made correctly
    mock_request.assert_called_once_with(
        "GET",
        "users_private",
        params={
            "select": "user_id",
            "api_key": f"eq.{good_async_client.session.headers['X-TWS-API-KEY']}",
        },
    )

    # Verify the user ID was returned and cached
    assert user_id == "test-user-123"
    assert good_async_client.user_id == "test-user-123"

    # Reset the mock and call again to verify caching
    mock_request.reset_mock()

    # Second call should use cached value
    user_id_again = await good_async_client._lookup_user_id()
    assert user_id_again == "test-user-123"

    # Verify no additional request was made
    mock_request.assert_not_called()


@patch("tws._async.client.AsyncClient._make_request")
async def test_lookup_user_id_empty_response(mock_request, good_async_client):
    # Mock empty response (no user found)
    mock_request.return_value = []

    with pytest.raises(ClientException) as exc_info:
        async with good_async_client:
            await good_async_client._lookup_user_id()

    assert "User ID not found, is your API key correct?" in str(exc_info.value)


@patch("tws._async.client.AsyncClient._make_request")
async def test_lookup_user_id_request_error(mock_request, good_async_client):
    # Mock request error
    mock_request.side_effect = Exception("Database connection error")

    with pytest.raises(ClientException) as exc_info:
        async with good_async_client:
            await good_async_client._lookup_user_id()

    assert "Failed to look up user ID: Database connection error" in str(exc_info.value)


@patch("tws._async.client.AsyncClient._make_request")
async def test_make_rpc_request_success(mock_request, good_async_client):
    mock_request.return_value = {"result": "success"}

    async with good_async_client:
        result = await good_async_client._make_rpc_request(
            "test_function", {"param": "value"}
        )

    mock_request.assert_called_once_with(
        "POST", "rpc/test_function", {"param": "value"}
    )
    assert result == {"result": "success"}


@patch("tws._async.client.AsyncClient._make_request")
async def test_make_rpc_request_without_payload(mock_request, good_async_client):
    mock_request.return_value = {"result": "success"}

    async with good_async_client:
        result = await good_async_client._make_rpc_request("test_function")

    mock_request.assert_called_once_with("POST", "rpc/test_function", None)
    assert result == {"result": "success"}


@patch("tws._async.client.AsyncClient._make_rpc_request")
@patch("tws._async.client.AsyncClient._make_request")
@patch("time.time")
async def test_run_workflow_timeout(
    mock_time, mock_request, mock_rpc, good_async_client
):
    # Mock successful workflow start
    mock_rpc.return_value = {"workflow_instance_id": "123"}

    # Mock running status
    mock_request.return_value = [{"status": "RUNNING", "result": None}]

    # Mock time to trigger timeout
    mock_time.side_effect = [0, 601]  # Start time and check time

    with pytest.raises(ClientException) as exc_info:
        async with good_async_client:
            await good_async_client.run_workflow(
                "workflow-id", {"arg": "value"}, timeout=600
            )
    assert "Workflow execution timed out after 600 seconds" in str(exc_info.value)


@patch("tws._async.client.AsyncClient._lookup_user_id")
@patch("tws._async.client.AsyncClient._make_request")
async def test_upload_file_success(
    mock_request, mock_lookup_user_id, good_async_client, tmp_path
):
    # Create a temporary test file
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("test content")

    # Mock user ID lookup
    mock_lookup_user_id.return_value = "test-user-456"

    # Mock successful file upload
    mock_request.return_value = {
        "Key": "documents/test-user-456/timestamp-test_file.txt"
    }

    async with good_async_client:
        file_path = await good_async_client._upload_file(str(test_file))

    # Verify the correct path is returned (without the documents/ prefix)
    assert file_path == "test-user-456/timestamp-test_file.txt"

    # Verify the file upload request was made with the correct parameters
    assert mock_request.call_count == 1
    # We can't check the exact file content in the call args because it's dynamic,
    # but we can verify the endpoint and service
    call_args = mock_request.call_args
    assert call_args[0][0] == "POST"  # HTTP method
    assert "object/documents/test-user-456/" in call_args[0][1]  # URI
    assert call_args[1]["service"] == "storage"  # service parameter


@patch("tws._async.client.AsyncClient._lookup_user_id")
async def test_upload_file_nonexistent_file(mock_lookup_user_id, good_async_client):
    # Mock user ID lookup
    mock_lookup_user_id.return_value = "test-user-456"

    with pytest.raises(ClientException) as exc_info:
        async with good_async_client:
            await good_async_client._upload_file("/nonexistent/file.txt")

    assert "File not found: /nonexistent/file.txt" in str(exc_info.value)


@patch("tws._async.client.AsyncClient._upload_file")
@patch("tws._async.client.AsyncClient._make_rpc_request")
@patch("tws._async.client.AsyncClient._make_request")
async def test_run_workflow_with_multiple_files(
    mock_request, mock_rpc, mock_upload, good_async_client, tmp_path
):
    # Create temporary test files
    test_file1 = tmp_path / "test_file1.txt"
    test_file1.write_text("test content 1")

    test_file2 = tmp_path / "test_file2.txt"
    test_file2.write_text("test content 2")

    # Mock file uploads with different return values for each file
    mock_upload.side_effect = [
        "user-123/timestamp-test_file1.txt",
        "user-123/timestamp-test_file2.txt",
    ]

    # Mock successful workflow start
    mock_rpc.return_value = {"workflow_instance_id": "123"}

    # Mock successful completion
    mock_request.return_value = [
        {"status": "COMPLETED", "result": {"output": "success with multiple files"}}
    ]

    files = {"input_file1": str(test_file1), "input_file2": str(test_file2)}

    async with good_async_client:
        result = await good_async_client.run_workflow(
            "workflow-id", {"arg": "value"}, files=files
        )

    # Verify both files were uploaded
    assert mock_upload.call_count == 2
    mock_upload.assert_any_call(str(test_file1))
    mock_upload.assert_any_call(str(test_file2))

    # Verify the file paths were merged into workflow args
    mock_rpc.assert_called_once_with(
        "start_workflow",
        {
            "workflow_definition_id": "workflow-id",
            "request_body": {
                "arg": "value",
                "input_file1": "user-123/timestamp-test_file1.txt",
                "input_file2": "user-123/timestamp-test_file2.txt",
            },
        },
    )
    assert result == {"output": "success with multiple files"}


@patch("tws._async.client.AsyncClient._upload_file")
@patch("tws._async.client.AsyncClient._make_rpc_request")
@patch("tws._async.client.AsyncClient._make_request")
async def test_run_workflow_with_files_and_tags(
    mock_request, mock_rpc, mock_upload, good_async_client, tmp_path
):
    # Create a temporary test file
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("test content")

    # Mock file upload
    mock_upload.return_value = "user-123/timestamp-test_file.txt"

    # Mock successful workflow start
    mock_rpc.return_value = {"workflow_instance_id": "123"}

    # Mock successful completion
    mock_request.return_value = [
        {"status": "COMPLETED", "result": {"output": "success with file and tags"}}
    ]

    files = {"input_file": str(test_file)}
    tags = {"tag1": "value1", "tag2": "value2"}

    async with good_async_client:
        result = await good_async_client.run_workflow(
            "workflow-id", {"arg": "value"}, files=files, tags=tags
        )

    # Verify file was uploaded
    mock_upload.assert_called_once_with(str(test_file))

    # Verify the file path was merged into workflow args and tags were included
    mock_rpc.assert_called_once_with(
        "start_workflow",
        {
            "workflow_definition_id": "workflow-id",
            "request_body": {
                "arg": "value",
                "input_file": "user-123/timestamp-test_file.txt",
            },
            "tags": tags,
        },
    )
    assert result == {"output": "success with file and tags"}
