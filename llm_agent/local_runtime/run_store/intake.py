import asyncio
import uuid
from uuid import UUID

from contracts.domain.runs.event import RunEvent
from llm_agent.domain.agent.runs.exception import RunNotFoundError
from llm_agent.domain.agent.runs.request import RunRequest
from contracts.domain.runs.status import RunStatus
from contracts.domain.runs.status_code import RunStatusCode, TERMINAL_RUN_STATUSES
from contracts.services.event_log import RunEventLog
from llm_agent.services.agent.store import RunIntakeStore
from llm_agent.services.agent.transition_policy import RunTransitionPolicy


class InMemoryRunIntakeStore(RunIntakeStore):
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
        TODO(event-sourcing): treat `_runs` as a projection/cache and derive `RunStatus` by folding the append-only `RunEventLog`.
        """
        self._runs = internal_run_storage
        self._events = internal_event_logs
        self._lock = asyncio.Lock()
        self.run_transition_policy = run_transition_policy

    async def create_run(self, run_request: RunRequest) -> RunStatus:
        """

        :param run_request:
        :return:
        """
        async with self._lock:
            run_id = uuid.uuid4()
            run_status = RunStatus(
                id=run_id,
                status=RunStatusCode.CREATED,
                result=None,
                error=None,
            )
            self._runs[run_id] = run_status
            await self._events.init_run_stream(run_id=run_id)
            await self._events.append(
                run_id=run_id,
                event_type="created",
                payload={
                    "user_id": run_request.user_id,
                },
            )
            return run_status

    async def get_status(self, run_id: UUID) -> RunStatus:
        if run_id not in self._runs:
            raise RunNotFoundError(run_id=str(run_id))
        return self._runs[run_id]

    async def mark_enqueued(self, run_id: UUID) -> None:
        async with self._lock:
            run_status = self._runs[run_id]
            self.run_transition_policy.validate(run_status, RunStatusCode.ENQUEUED)

            self._runs[run_id] = RunStatus(
                id=run_status.id,
                status=RunStatusCode.ENQUEUED,
                result=run_status.result,
                error=run_status.error,
            )
            await self._events.append(
                run_id=run_id,
                event_type="enqueued",
                payload={},
            )

    async def mark_cancelled(self, run_id: UUID) -> bool:
        """
        DEPRECATED
        :param run_id:
        :return:
        :raises: RunNotFoundError
        """
        async with self._lock:
            if run_id not in self._runs:
                raise RunNotFoundError(run_id=str(run_id))
            run_status = self._runs[run_id]
            if run_status.status in TERMINAL_RUN_STATUSES:
                return False

            self.run_transition_policy.validate(run_status, RunStatusCode.CANCELLED)

            self._runs[run_id] = RunStatus(
                id=run_status.id,
                status=RunStatusCode.CANCELLED,
                result=run_status.result,
                error=run_status.error,
            )
            await self._events.append(
                run_id=run_id,
                event_type="cancelled",
                payload={},
            )
            return True

    async def request_cancellation(self, run_id: UUID) -> bool:
        async with self._lock:
            if run_id not in self._runs:
                raise RunNotFoundError(run_id=str(run_id))
            run_status = self._runs[run_id]
            if run_status.status in TERMINAL_RUN_STATUSES:
                return False
            if run_status.cancel_requested:
                return False

            self._runs[run_id] = RunStatus(
                id=run_status.id,
                status=run_status.status,
                result=run_status.result,
                error=run_status.error,
                cancel_requested=True,
                claimed_worker=run_status.claimed_worker,
                claim_expiration_unix_ts=run_status.claim_expiration_unix_ts,
                retry_count=run_status.retry_count,
            )
            await self._events.append(
                run_id=run_id,
                event_type="cancel requested",
                payload={},
            )
            return True

    async def get_events(self, run_id: UUID, *, after_sequence: int | None = None) -> list[RunEvent]:
        """
        Retrieve events for a run from the event log.

        :param run_id: The run ID
        :param after_sequence: Optional sequence number to filter events after
        :return: List of run events
        :raises: RunNotFoundError if the run is not found
        :raises: ValueError if event log is not available
        """
        # Verify run exists first
        if run_id not in self._runs:
            raise RunNotFoundError(run_id=str(run_id))
        return await self._events.list(run_id=run_id, after_sequence=after_sequence)
