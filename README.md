# `tws-sdk`

Python client for [TWS](https://www.tuneni.ai).

## Installation

```bash
pip install tws-sdk
```

## Usage

The library provides both synchronous and asynchronous clients for interacting with TWS.

The primary API is `run_workflow`, which executes a workflow configured via the TWS UI, waits for completion,
and returns the result.

### Synchronous Usage

```python
from tws import Client as TWSClient

# Use the client with a context manager
with TWSClient(
    public_key="your_public_key",
    secret_key="your_secret_key",
    api_url="your_api_url"
) as tws_client:
    # Run a workflow and wait for completion
    result = tws_client.run_workflow(
        workflow_definition_id="your_workflow_id",
        workflow_args={
            "param1": "value1",
            "param2": "value2"
        },
    )
```

### Asynchronous Usage

The signatures are exactly the same for async usage, but the client class is `TWSAsyncClient` and client
methods are awaited.

```python
from tws import AsyncClient as TWSAsyncClient


async def main():
    # Use the async client with a context manager
    async with TWSAsyncClient(
        public_key="your_public_key",
        secret_key="your_secret_key",
        api_url="your_api_url"
    ) as tws_client:
        # Run a workflow and wait for completion
        result = await tws_client.run_workflow(
            workflow_definition_id="your_workflow_id",
            workflow_args={
                "param1": "value1",
                "param2": "value2"
            },
        )
```

### Tags

You can specify tags, which are string key-value pairs, when calling the `run_workflow` method. These tags can then
be used when designing workflows in TWS to lookup and filter the results of workflow runs. This allows you to associate
the results of a workflow run with a specific entity or grouping mechanism within your system, such as a user ID or
a lesson ID.

Provide tags to the `run_workflow` method as a dictionary. Keep in mind that both tag keys and values must be strings
that are at most 255 characters long.

```python
tws_client.run_workflow(
    workflow_definition_id="your_workflow_id",
    workflow_args={
        "param1": "value1",
        "param2": "value2"
    },
    tags={
        "user_id": "12345",
        "lesson_id": "67890"
    }
)
```
