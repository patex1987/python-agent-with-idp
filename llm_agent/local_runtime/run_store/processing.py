import asyncio
import datetime
from uuid import UUID

import structlog

from agent_run_worker.domain.exception import RunLeaseLostError
from agent_run_worker.domain.runs.claim import ClaimedRun
from contracts.domain.runs.event import RunEvent
from llm_agent.domain.agent.runs.exception import RunNotFoundError
from contracts.domain.runs.status import RunStatus
from contracts.domain.runs.status_code import RunStatusCode
from llm_agent.domain.agent.runs.transition_request import TransitionRequestParams, get_value_or_fallback
from contracts.services.event_log import RunEventLog
from agent_run_worker.services.runs.processing_store import RunProcessingStore
from llm_agent.services.agent.transition_policy import RunTransitionPolicy

logger = structlog.getLogger(__name__)


class InMemoryRunProcessingStore(RunProcessingStore):
    def __init__(
        self,
        internal_run_storage: dict[UUID, RunStatus],
        internal_event_logs: RunEventLog,
        run_transition_policy: RunTransitionPolicy,
    ):
        """

        :param internal_run_storage: injectable from the outside, i.e. possible
            to share with the worker
        :param internal_event_logs: something like transactional logs for
            events (append only)
        """
        self._runs = internal_run_storage
        self._events = internal_event_logs
        self._lock = asyncio.Lock()
        self.run_transition_policy = run_transition_policy

    async def claim_run(self, worker_id: str) -> ClaimedRun | None:
        """


        Querying is ineffective, but remember this is an in-memory POC
        Needs to be atomic to handle concurrency on multiple workers

        :param worker_id:
        :return:
        """
        async with self._lock:
            for run_id, run_status in self._runs.items():
                if run_status.status != RunStatusCode.RUNNING:
                    continue
                claim_expired = has_claim_expired(run_status)
                if not claim_expired:
                    continue
                logger.info(f"Run claim on {run_id} expired, retrying")
                await self._events.append(
                    run_id=run_id,
                    event_type="claim_expired",
                    payload={},
                )
                await self.recover_expired_runs(run_id, run_status, worker_id)

            for run_id, run_status in self._runs.items():
                if run_status.status == RunStatusCode.ENQUEUED:
                    if run_status.cancel_requested:
                        await self._set_cancelled_locked(run_id)
                        continue

                    expiration_unix_ts = await get_new_expiration_ts()
                    transition_request = TransitionRequestParams(
                        worker_id=worker_id, expiration_unix_ts=expiration_unix_ts
                    )
                    await self._transition_locked(run_id, RunStatusCode.RUNNING, transition_request=transition_request)
                    logger.info(f"Run {run_id} claimed by {worker_id}")
                    await self._events.append(
                        run_id=run_id,
                        event_type="claimed",
                        payload={"worker": str(worker_id)},
                    )
                    return ClaimedRun(id=run_id, claim_type="enqueued", run_status=self._runs[run_id])

            return None

    async def append_event(self, evt: RunEvent) -> None: ...

    async def heartbeat(self, run_id: UUID, worker_id: str) -> RunStatus:
        """
        Extend the expiration time of a running run claimed by a given worker.

        :param run_id:
        :param worker_id:
        :return:
        :raises: RunLeaseLostError - when the run is claimed by a different worker
        """
        async with self._lock:
            run_status = self._runs[run_id]

            if run_status.status == RunStatusCode.CANCELLED:
                return run_status

            if run_status.status != RunStatusCode.RUNNING:
                return run_status

            if run_status.claimed_worker != worker_id:
                await self._events.append(
                    run_id=run_id,
                    event_type="claim_lost",
                    payload={"worker": str(worker_id)},
                )
                raise RunLeaseLostError(f"Run {run_id} is not claimed by {worker_id}")

            updated_expiration_unix_ts = await get_new_expiration_ts()

            updated_run_status = RunStatus(
                id=run_status.id,
                status=RunStatusCode.RUNNING,
                result=run_status.result,
                error=run_status.error,
                claimed_worker=worker_id,
                claim_expiration_unix_ts=updated_expiration_unix_ts,
                retry_count=run_status.retry_count,
                cancel_requested=run_status.cancel_requested,
            )
            self._runs[run_id] = updated_run_status
            return updated_run_status

    async def set_failed(self, run_id: UUID, error: str) -> None:
        async with self._lock:
            transition_request = TransitionRequestParams(error=error)
            await self._transition_locked(run_id, RunStatusCode.FAILED, transition_request=transition_request)
            await self._events.append(
                run_id=run_id,
                event_type="run_failed",
                payload={"error": error},
            )

    async def set_succeeded(self, run_id: UUID, result: dict) -> None:
        async with self._lock:
            transition_request = TransitionRequestParams(result=result)
            await self._transition_locked(run_id, RunStatusCode.SUCCEEDED, transition_request=transition_request)
            await self._events.append(
                run_id=run_id,
                event_type="run_succeeded",
                payload={"result": "done"},
            )

    async def get_status(self, run_id: UUID) -> RunStatus:
        async with self._lock:
            if run_id not in self._runs:
                raise RunNotFoundError(run_id=str(run_id))
            return self._runs[run_id]

    async def set_cancelled(self, run_id: UUID) -> None:
        """
        Sets the run status to canceled definitively.

        :param run_id:
        :return:
        """
        async with self._lock:
            await self._set_cancelled_locked(run_id)

    async def recover_expired_runs(self, run_id, run_status, worker_id):
        """
        Recover a run whose lease has expired.

        This handles two scenarios:
        1. Normal lease expiration (worker crashed, network issue, etc.)
        2. Worker shutdown (worker gracefully shuts down, stops heartbeating, lease expires)

        Recovery flow: TIMED_OUT → RETRYING → ENQUEUED
        This allows the run to be picked up by another worker.

        Note: This is different from explicit cancellation (mark_cancelled),
        which transitions to CANCELLED status and does not allow retries.
        """
        logger.info(f"Run {run_id} expired, originally assigned to {run_status.claimed_worker}")
        transition_request = TransitionRequestParams(worker_id=worker_id)
        await self._transition_locked(run_id, RunStatusCode.TIMED_OUT, transition_request=transition_request)
        updated_retry = TransitionRequestParams(worker_id=worker_id, retry_count=run_status.retry_count + 1)
        await self._transition_locked(run_id, RunStatusCode.RETRYING, transition_request=updated_retry)
        await self._transition_locked(run_id, RunStatusCode.ENQUEUED, transition_request=transition_request)

    async def _set_cancelled_locked(self, run_id: UUID) -> None:
        """
        Internal: Sets run status to cancelled. Expects lock to be held.
        """
        transition_request = TransitionRequestParams()
        logger.info("Run cancelled", run_id=run_id)
        await self._transition_locked(run_id, RunStatusCode.CANCELLED, transition_request=transition_request)
        await self._events.append(
            run_id=run_id,
            event_type="cancelled",
            payload={},
        )

    async def _transition_locked(
        self,
        run_id: UUID,
        target_status: RunStatusCode,
        *,
        transition_request: TransitionRequestParams | None = None,
    ):
        """
        Transition the run to the desired state.

        Expects that a lock is held over the given entity.
        :param run_id:
        :param target_status:
        :param transition_request:
        :return:
        """
        run_status = self._runs[run_id]
        if not transition_request:
            transition_request = TransitionRequestParams()

        self.run_transition_policy.validate(run_status, target_status)

        result = get_value_or_fallback(transition_request.result, run_status.result)
        error = get_value_or_fallback(transition_request.error, run_status.error)
        worker_id = get_value_or_fallback(transition_request.worker_id, run_status.claimed_worker)
        claim_expiration_unix_ts = get_value_or_fallback(
            transition_request.expiration_unix_ts, run_status.claim_expiration_unix_ts
        )
        retry_count = get_value_or_fallback(transition_request.retry_count, run_status.retry_count)

        self._runs[run_id] = RunStatus(
            id=run_status.id,
            status=target_status,
            result=result,
            error=error,
            claimed_worker=worker_id,
            claim_expiration_unix_ts=claim_expiration_unix_ts,
            retry_count=retry_count,
            cancel_requested=run_status.cancel_requested,
        )


def has_claim_expired(run_status: RunStatus) -> bool:
    if not run_status.claim_expiration_unix_ts:
        return False
    current_unix_ts = datetime.datetime.now(tz=datetime.UTC).timestamp()
    if current_unix_ts > run_status.claim_expiration_unix_ts:
        return True
    return False


async def get_new_expiration_ts() -> float:
    expiration_unix_ts = datetime.datetime.now(tz=datetime.UTC).timestamp() + 30
    return expiration_unix_ts
