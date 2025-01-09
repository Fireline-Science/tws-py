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
