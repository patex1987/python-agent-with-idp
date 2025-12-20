import svcs

from llm_agent.di.registrars.base import Registrar
from llm_agent.infrastructure.agent.in_memory.queue import InMemoryJobSignalQueue

from llm_agent.services.agent.orchestrator import BackendJobOrchestrationService
from llm_agent.services.agent.queue import JobSignalQueue
from llm_agent.services.agent.store import JobIntakeStore
from tests.fake_implementations.di.factories.job_related import (
    InternalJobStorageProvider,
    InternalEventLogsProvider,
)


class InMemoryJobOrchestrationRegistrar(Registrar):
    def register(self, registry: svcs.Registry) -> None:
        job_store = self.__class__.create_job_store()
        job_signal_queue = self.__class__.create_job_signal_queue()

        registry.register_value(JobIntakeStore, job_store)
        registry.register_value(JobSignalQueue, job_signal_queue)

        job_orchestrator = BackendJobOrchestrationService(
            job_store=job_store,
            job_signal_queue=job_signal_queue,
        )
        registry.register_value(BackendJobOrchestrationService, job_orchestrator)

    @classmethod
    def create_job_store(cls) -> JobIntakeStore:
        """
        create a job store, with shared internal storage.

        So the worker can see inside the content in a single process setup.
        """
        from llm_agent.infrastructure.agent.in_memory.store import InMemoryJobIntakeStore

        internal_job_storage = InternalJobStorageProvider.get_instance()
        internal_event_logs = InternalEventLogsProvider.get_instance()

        in_memory_job_store = InMemoryJobIntakeStore(
            internal_job_storage=internal_job_storage,
            internal_event_logs=internal_event_logs,
        )
        return in_memory_job_store

    @classmethod
    def create_job_signal_queue(cls) -> JobSignalQueue:
        """
        Create an in-memory job queue with shared storage.

        So the worker can see inside the content in a single process setup.
        """
        in_memory_job_queue = InMemoryJobSignalQueue()
        return in_memory_job_queue
