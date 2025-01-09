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
from tws import ClientException, Client


@pytest.fixture
def good_client():
    return Client(GOOD_PUBLIC_KEY, GOOD_SECRET_KEY, GOOD_URL)


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
        with Client(public_key, secret_key, api_url):
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
def test_run_workflow_validation(good_client, timeout, retry_delay, exception_message):
    with pytest.raises(ClientException) as exc_info:
        with good_client:
            good_client.run_workflow(
                "workflow-id",
                {"arg": "value"},
                timeout=timeout,
                retry_delay=retry_delay,
            )
    assert exception_message in str(exc_info.value)


@patch("tws._sync.client.SyncClient._make_rpc_request")
def test_run_workflow_not_found(mock_rpc, good_client):
    mock_request = Request("POST", "http://example.com")
    mock_response = Response(400, request=mock_request)
    mock_response._content = b'{"code": "P0001"}'  # type: ignore

    mock_rpc.side_effect = HTTPStatusError(
        "400 Bad Request", request=mock_request, response=mock_response
    )

    with pytest.raises(ClientException) as exc_info:
        with good_client:
            good_client.run_workflow("non-existent-workflow", {"arg": "value"})
    assert "Workflow definition ID not found" in str(exc_info.value)


@patch("tws._sync.client.SyncClient._make_rpc_request")
def test_run_workflow_bad_request(mock_rpc, good_client):
    mock_request = Request("POST", "http://example.com")
    mock_response = Response(400, request=mock_request)
    mock_response._content = b'{"message": "Bad request", "code": "PXXXX"}'  # type: ignore

    mock_rpc.side_effect = HTTPStatusError(
        "Bad request", request=mock_request, response=mock_response
    )

    with pytest.raises(ClientException) as exc_info:
        with good_client:
            good_client.run_workflow("workflow-id", {"bad": "args"})
    assert "Bad request" in str(exc_info.value)


@patch("tws._sync.client.SyncClient._make_rpc_request")
@patch("tws._sync.client.SyncClient._make_request")
def test_run_workflow_success(mock_request, mock_rpc, good_client):
    # Mock successful workflow start
    mock_rpc.return_value = {"workflow_instance_id": "123"}

    # Mock successful completion
    mock_request.return_value = [
        {"status": "COMPLETED", "result": {"output": "success"}}
    ]

    with good_client:
        result = good_client.run_workflow("workflow-id", {"arg": "value"})
    assert result == {"output": "success"}


@patch("tws._sync.client.SyncClient._make_rpc_request")
@patch("tws._sync.client.SyncClient._make_request")
@patch("time.sleep")
@patch("time.time")
def test_run_workflow_success_after_polling(
    mock_time, mock_sleep, mock_request, mock_rpc, good_client
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

    with good_client:
        result = good_client.run_workflow("workflow-id", {"arg": "value"})

    # Verify sleep was called once with retry_delay
    mock_sleep.assert_called_once_with(1)
    assert result == {"output": "success after poll"}


@patch("tws._sync.client.SyncClient._make_rpc_request")
@patch("tws._sync.client.SyncClient._make_request")
def test_run_workflow_failure(mock_request, mock_rpc, good_client):
    # Mock successful workflow start
    mock_rpc.return_value = {"workflow_instance_id": "123"}

    # Mock failed execution
    mock_request.return_value = [
        {"status": "FAILED", "result": {"error": "workflow failed"}}
    ]

    with pytest.raises(ClientException) as exc_info:
        with good_client:
            good_client.run_workflow("workflow-id", {"arg": "value"})
    assert "Workflow execution failed" in str(exc_info.value)


@patch("tws._sync.client.SyncClient._make_rpc_request")
@patch("tws._sync.client.SyncClient._make_request")
def test_run_workflow_instance_not_found(mock_request, mock_rpc, good_client):
    # Mock successful workflow start
    mock_rpc.return_value = {"workflow_instance_id": "123"}

    # Mock instance not found
    mock_request.return_value = []

    with pytest.raises(ClientException) as exc_info:
        with good_client:
            good_client.run_workflow("workflow-id", {"arg": "value"})
    assert "Workflow instance 123 not found" in str(exc_info.value)


@patch("httpx.Client.request")
def test_make_request_success(mock_request, good_client):
    mock_response = mock_request.return_value
    mock_response.raise_for_status = lambda: None

    def mock_json():
        return {"data": "test"}

    mock_response.json = mock_json

    with good_client:
        result = good_client._make_request(
            "GET", "test/endpoint", {"param": "value"}, {"query": "param"}
        )

    mock_request.assert_called_once_with(
        "GET",
        "/rest/v1/test/endpoint",
        json={"param": "value"},
        params={"query": "param"},
    )
    assert result == {"data": "test"}


@patch("httpx.Client.request")
def test_make_request_error(mock_request, good_client):
    mock_request.side_effect = httpx.RequestError("Network error")

    with pytest.raises(ClientException) as exc_info:
        with good_client:
            good_client._make_request("GET", "test/endpoint")

    assert "Request error occurred: Network error" in str(exc_info.value)


@patch("tws._sync.client.SyncClient._make_request")
def test_make_rpc_request_success(mock_request, good_client):
    mock_request.return_value = {"result": "success"}

    with good_client:
        result = good_client._make_rpc_request("test_function", {"param": "value"})

    mock_request.assert_called_once_with(
        "POST", "rpc/test_function", {"param": "value"}
    )
    assert result == {"result": "success"}


@patch("tws._sync.client.SyncClient._make_request")
def test_make_rpc_request_without_payload(mock_request, good_client):
    mock_request.return_value = {"result": "success"}

    with good_client:
        result = good_client._make_rpc_request("test_function")

    mock_request.assert_called_once_with("POST", "rpc/test_function", None)
    assert result == {"result": "success"}


@patch("tws._sync.client.SyncClient._make_rpc_request")
@patch("tws._sync.client.SyncClient._make_request")
@patch("time.time")
def test_run_workflow_timeout(mock_time, mock_request, mock_rpc, good_client):
    # Mock successful workflow start
    mock_rpc.return_value = {"workflow_instance_id": "123"}

    # Mock running status
    mock_request.return_value = [{"status": "RUNNING", "result": None}]

    # Mock time to trigger timeout
    mock_time.side_effect = [0, 601]  # Start time and check time

    with pytest.raises(ClientException) as exc_info:
        with good_client:
            good_client.run_workflow("workflow-id", {"arg": "value"}, timeout=600)
    assert "Workflow execution timed out after 600 seconds" in str(exc_info.value)
