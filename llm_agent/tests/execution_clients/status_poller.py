import asyncio
import time
from typing import Any

from httpx import AsyncClient
from starlette.testclient import TestClient

from contracts.domain.runs.status_code import TERMINAL_RUN_STATUSES


def poll_run_status(
    client: TestClient,
    run_id: str,
    timeout_seconds: float = 60.0,
    initial_interval: float = 0.1,
    max_interval: float = 2.0,
    backoff_factor: float = 1.5,
) -> dict:
    """
    Poll run status until terminal state or timeout.

    Uses exponential backoff to avoid excessive polling while still
    being responsive to quick completions.

    :param client: TestClient instance
    :param run_id: Run ID to poll
    :param timeout_seconds: Maximum time to wait
    :param initial_interval: Initial polling interval in seconds
    :param max_interval: Maximum polling interval in seconds
    :param backoff_factor: Multiplier for exponential backoff
    :return: raw run response
    :raises: TimeoutError If run doesn't reach terminal state within timeout

    TODO: move this to a common test polling logic
    TODO: (stretch) use a well-known exponential backoff lib
    """
    start_time = time.time()
    interval = initial_interval
    last_status = None

    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            raise TimeoutError(
                f"Run {run_id} did not reach terminal state within {timeout_seconds}s. Last status: {last_status}"
            )

        response = client.get(f"/api/v1/agent/runs/{run_id}")
        response.raise_for_status()  # Raises for 4xx/5xx

        status_data = response.json()
        status = status_data["status"]
        last_status = status

        # Check if we've reached a terminal state
        if status in {run_status.name for run_status in TERMINAL_RUN_STATUSES}:
            return status_data

        # Exponential backoff: increase interval up to max
        time.sleep(interval)
        interval = min(interval * backoff_factor, max_interval)


async def poll_run_status_async(
    client: AsyncClient,
    run_id: str,
    timeout_seconds: float = 60.0,
    initial_interval: float = 0.1,
    max_interval: float = 2.0,
    backoff_factor: float = 1.5,
) -> dict[str, Any]:
    """
    Poll run status until terminal state or timeout.

    Uses exponential backoff to avoid excessive polling while still
    being responsive to quick completions.

    :param client: AsyncClient instance
    :param run_id: Run ID to poll
    :param timeout_seconds: Maximum time to wait
    :param initial_interval: Initial polling interval in seconds
    :param max_interval: Maximum polling interval in seconds
    :param backoff_factor: Multiplier for exponential backoff
    :return: raw run response
    :raises TimeoutError: If run doesn't reach terminal state within timeout

    TODO: move this to a common test polling logic
    TODO: (stretch) use a well-known exponential backoff lib
    """
    start_time = time.monotonic()
    interval = initial_interval
    last_status = None

    while True:
        elapsed = time.monotonic() - start_time
        if elapsed > timeout_seconds:
            raise TimeoutError(
                f"Run {run_id} did not reach terminal state within {timeout_seconds}s. Last status: {last_status}"
            )

        response = await client.get(f"/api/v1/agent/runs/{run_id}")
        response.raise_for_status()

        status_data = response.json()
        status = status_data["status"]
        last_status = status

        if status in {run_status.name for run_status in TERMINAL_RUN_STATUSES}:
            return status_data

        await asyncio.sleep(interval)
        interval = min(interval * backoff_factor, max_interval)


def sync_wait_until(predicate, *, timeout=2.0, interval=0.01, what="condition"):
    """
    Polls the given predicate until it becomes true, or times out.

    utility to be used in tests when waiting for signals

    :param predicate:
    :param timeout:
    :param interval:
    :param what:
    :return:
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(interval)
    raise TimeoutError(f"Timed out waiting for {what}")
