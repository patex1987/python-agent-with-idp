import uuid

import svcs

from agent_job_worker.in_memory.consumer import Consumer, InMemoryConsumer
from agent_job_worker.in_memory.job_executor import DummyJobExecutor, AgentJobExecutor, RandomSleepJobExecutor
from llm_agent.di.registrars.base import Registrar
from llm_agent.infrastructure.agent.in_memory.store import InMemoryJobProcessingStore
from llm_agent.services.agent.queue import JobSignalQueue
from llm_agent.services.agent.store import JobProcessingStore
from llm_agent.services.agent.transition_policy import JobTransitionPolicy
from tests.fake_implementations.llm_agent.di.factories.job_related import (
    JobSignalQueueProvider,
    InternalJobStorageProvider,
    InternalEventLogsProvider,
)


class ConsumerRegistrar(Registrar):
    def register(self, registry: svcs.Registry) -> None:
        registry.register_factory(AgentJobExecutor, RandomSleepJobExecutor)
        job_signal_queue = self.get_job_signal_queue()
        job_store = self.get_job_store()
        registry.register_value(JobSignalQueue, job_signal_queue)
        registry.register_value(JobProcessingStore, job_store)
        registry.register_factory(Consumer, self.get_consumer)

    def get_job_signal_queue(self) -> JobSignalQueue:
        return JobSignalQueueProvider.get_instance()

    def get_job_store(self) -> JobProcessingStore:
        return InMemoryJobProcessingStore(
            internal_job_storage=InternalJobStorageProvider.get_instance(),
            internal_event_logs=InternalEventLogsProvider.get_instance(),
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
        )
