import asyncio
import time
from typing import Any

from httpx import AsyncClient
from starlette.testclient import TestClient

from llm_agent.domain.agent.jobs.status_code import TERMINAL_JOB_STATUSES


def poll_job_status(
    client: TestClient,
    job_id: str,
    timeout_seconds: float = 60.0,
    initial_interval: float = 0.1,
    max_interval: float = 2.0,
    backoff_factor: float = 1.5,
) -> dict:
    """
    Poll job status until terminal state or timeout.

    Uses exponential backoff to avoid excessive polling while still
    being responsive to quick completions.

    :param client: TestClient instance
    :param job_id: Job ID to poll
    :param timeout_seconds: Maximum time to wait
    :param initial_interval: Initial polling interval in seconds
    :param max_interval: Maximum polling interval in seconds
    :param backoff_factor: Multiplier for exponential backoff
    :return: raw job response
    :raises: TimeoutError If job doesn't reach terminal state within timeout

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
                f"Job {job_id} did not reach terminal state within {timeout_seconds}s. Last status: {last_status}"
            )

        response = client.get(f"/api/v1/agent/get-job-status/{job_id}")
        response.raise_for_status()  # Raises for 4xx/5xx

        status_data = response.json()
        status = status_data["status"]
        last_status = status

        # Check if we've reached a terminal state
        if status in {job_status.name for job_status in TERMINAL_JOB_STATUSES}:
            return status_data

        # Exponential backoff: increase interval up to max
        time.sleep(interval)
        interval = min(interval * backoff_factor, max_interval)


async def poll_job_status_async(
    client: AsyncClient,
    job_id: str,
    timeout_seconds: float = 60.0,
    initial_interval: float = 0.1,
    max_interval: float = 2.0,
    backoff_factor: float = 1.5,
) -> dict[str, Any]:
    """
    Poll job status until terminal state or timeout.

    Uses exponential backoff to avoid excessive polling while still
    being responsive to quick completions.

    :param client: AsyncClient instance
    :param job_id: Job ID to poll
    :param timeout_seconds: Maximum time to wait
    :param initial_interval: Initial polling interval in seconds
    :param max_interval: Maximum polling interval in seconds
    :param backoff_factor: Multiplier for exponential backoff
    :return: raw job response
    :raises TimeoutError: If job doesn't reach terminal state within timeout

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
                f"Job {job_id} did not reach terminal state within "
                f"{timeout_seconds}s. Last status: {last_status}"
            )

        response = await client.get(f"/api/v1/agent/get-job-status/{job_id}")
        response.raise_for_status()

        status_data = response.json()
        status = status_data["status"]
        last_status = status

        if status in {job_status.name for job_status in TERMINAL_JOB_STATUSES}:
            return status_data

        await asyncio.sleep(interval)
        interval = min(interval * backoff_factor, max_interval)