# `tws-py`

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
from tws import create_client

# Create a client instance
client = create_client(
    public_key="your_public_key",
    secret_key="your_secret_key",
    api_url="your_api_url"
)

# Run a workflow and wait for completion
result = client.run_workflow(
    workflow_definition_id="your_workflow_id",
    workflow_args={
        "param1": "value1",
        "param2": "value2"
    },
)
```

### Asynchronous Usage

The signatures are exactly the same for async usage, but the client is created using `create_async_client` and client
methods are awaited.

```python
from tws import create_async_client


async def main():
    # Create an async client instance
    client = await create_async_client(
        public_key="your_public_key",
        secret_key="your_secret_key",
        api_url="your_api_url"
    )

    # Run a workflow and wait for completion
    result = await client.run_workflow(
        workflow_definition_id="your_workflow_id",
        workflow_args={
            "param1": "value1",
            "param2": "value2"
        },
    )
```