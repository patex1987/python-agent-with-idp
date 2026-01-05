import uuid

import svcs

from agent_job_worker.in_memory.consumer import Consumer, InMemoryConsumer
from agent_job_worker.in_memory.job_executor import AgentJobExecutor, RandomSleepJobExecutor
from llm_agent.di.registrars.base import Registrar
from local_runtime.job_store.processing import InMemoryJobProcessingStore
from llm_agent.services.agent.queue import JobSignalQueue
from llm_agent.services.agent.store import JobProcessingStore
from llm_agent.services.agent.transition_policy import JobTransitionPolicy
from local_runtime.provider import InMemoryRuntime


class ConsumerRegistrar(Registrar):
    def __init__(self, shared_local_infrastructure: InMemoryRuntime):
        self._shared_local_infrastructure = shared_local_infrastructure

    def register(self, registry: svcs.Registry) -> None:
        registry.register_factory(AgentJobExecutor, RandomSleepJobExecutor)
        job_signal_queue = self.get_job_signal_queue()
        job_store = self.get_job_store()
        registry.register_value(JobSignalQueue, job_signal_queue)
        registry.register_value(JobProcessingStore, job_store)
        registry.register_factory(Consumer, self.get_consumer)

    def get_job_signal_queue(self) -> JobSignalQueue:
        return self._shared_local_infrastructure.job_signal_queue

    def get_job_store(self) -> JobProcessingStore:
        internal_job_storage = self._shared_local_infrastructure.internal_job_storage
        internal_event_logs = self._shared_local_infrastructure.internal_event_logs

        return InMemoryJobProcessingStore(
            internal_job_storage=internal_job_storage,
            internal_event_logs=internal_event_logs,
            job_transition_policy=JobTransitionPolicy(),
        )

    @classmethod
    def get_consumer(cls, svcs_container: svcs.Container) -> Consumer:
        worker_id = f"worker_{uuid.uuid4()}"
        return InMemoryConsumer(
            job_store=svcs_container.get(JobProcessingStore),
            job_signal_queue=svcs_container.get(JobSignalQueue),
            worker_id=worker_id,
            job_executor=svcs_container.get(AgentJobExecutor),
            heartbeat_interval_seconds=5,
        )
